import maya.cmds as cmds

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

COLOR_RED    = 13
COLOR_ORANGE = 17
COLOR_BLUE   = 6
COLOR_YELLOW = 16

LO_SPANS  = 3
MID_SPANS = LO_SPANS * 2

MID_PARAMS = {
    2: [0.75, 2.25],
    4: [0.5,  1.0,  2.0,  2.5],
    6: [0.375, 0.75, 1.125, 1.875, 2.25, 2.625],
}


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _set_color(node, color_index):
    cmds.setAttr("{}.overrideEnabled".format(node), 1)
    cmds.setAttr("{}.overrideColor".format(node),   color_index)


def _get_curve_shape(curve_transform):
    shapes = cmds.listRelatives(curve_transform, shapes=True, type="nurbsCurve") or []
    for s in shapes:
        if not cmds.getAttr("{}.intermediateObject".format(s)):
            return s
    raise RuntimeError("No nurbsCurve shape under: {}".format(curve_transform))


def _rebuild_curve(curve, spans, name):
    cmds.rebuildCurve(
        curve,
        ch=False, rpo=True,
        rt=0, end=2, kr=2,
        kcp=False, kep=False, kt=False,
        s=spans, d=3, tol=0.01,
    )
    return cmds.rename(curve, name)


def _bake_curve_point(curve_shape, param):
    tmp_loc  = cmds.spaceLocator(name="_tmp_bake_loc")[0]
    tmp_poci = cmds.createNode("pointOnCurveInfo", name="_tmp_bake_poci")
    tmp_fbfm = cmds.createNode("fourByFourMatrix",  name="_tmp_bake_fbfm")
    tmp_dcm  = cmds.createNode("decomposeMatrix",   name="_tmp_bake_dcm")

    cmds.setAttr("{}.turnOnPercentage".format(tmp_poci), False)
    cmds.setAttr("{}.parameter".format(tmp_poci), param)
    cmds.connectAttr("{}.worldSpace[0]".format(curve_shape),
                     "{}.inputCurve".format(tmp_poci))

    for row, (tx, ty, tz) in enumerate([
            ("tangentX", "tangentY", "tangentZ"),
            ("normalX",  "normalY",  "normalZ")]):
        cmds.connectAttr("{}.{}".format(tmp_poci, tx), "{}.in{}0".format(tmp_fbfm, row))
        cmds.connectAttr("{}.{}".format(tmp_poci, ty), "{}.in{}1".format(tmp_fbfm, row))
        cmds.connectAttr("{}.{}".format(tmp_poci, tz), "{}.in{}2".format(tmp_fbfm, row))

    cmds.connectAttr("{}.output".format(tmp_fbfm),      "{}.inputMatrix".format(tmp_dcm))
    cmds.connectAttr("{}.position".format(tmp_poci),    "{}.translate".format(tmp_loc))
    cmds.connectAttr("{}.outputRotate".format(tmp_dcm), "{}.rotate".format(tmp_loc))

    pos = cmds.xform(tmp_loc, q=True, ws=True, t=True)
    rot = cmds.xform(tmp_loc, q=True, ws=True, ro=True)

    cmds.delete(tmp_loc, tmp_dcm, tmp_fbfm, tmp_poci)
    return pos, rot


def _build_orient_network(poci, label):
    fbfm = cmds.createNode("fourByFourMatrix", name="fbfMtx_{}".format(label))
    for row, (tx, ty, tz) in enumerate([
            ("tangentX", "tangentY", "tangentZ"),
            ("normalX",  "normalY",  "normalZ")]):
        cmds.connectAttr("{}.{}".format(poci, tx), "{}.in{}0".format(fbfm, row))
        cmds.connectAttr("{}.{}".format(poci, ty), "{}.in{}1".format(fbfm, row))
        cmds.connectAttr("{}.{}".format(poci, tz), "{}.in{}2".format(fbfm, row))

    dcm = cmds.createNode("decomposeMatrix", name="decMtx_{}".format(label))
    cmds.connectAttr("{}.output".format(fbfm), "{}.inputMatrix".format(dcm))
    return fbfm, dcm


def _build_driver_joint(curve_shape, param, label, parent_grp, color):
    jnt_name = "jnt_drv_{}".format(label)
    pos, rot = _bake_curve_point(curve_shape, param)

    cmds.select(cl=True)
    jnt = cmds.joint(name=jnt_name)
    cmds.xform(jnt, ws=True, t=pos)
    cmds.xform(jnt, ws=True, ro=rot)
    _set_color(jnt, color)

    off = cmds.group(em=True, name="off_{}".format(jnt_name))
    cmds.xform(off, ws=True, t=pos)
    cmds.xform(off, ws=True, ro=rot)

    trans_off = cmds.group(em=True, name="transOff_{}".format(jnt_name))
    cmds.parent(trans_off, off)
    cmds.parent(jnt, trans_off)
    cmds.setAttr("{}.translate".format(trans_off), 0, 0, 0)
    cmds.setAttr("{}.rotate".format(trans_off),    0, 0, 0)
    cmds.setAttr("{}.translate".format(jnt), 0, 0, 0)
    cmds.setAttr("{}.rotate".format(jnt),    0, 0, 0)

    cmds.parent(off, parent_grp)
    cmds.select(cl=True)
    return off, jnt


def _build_target_group(curve_shape, param, label):
    tgt_grp = cmds.group(em=True, name="tgt_{}".format(label))

    init_pos, _ = _bake_curve_point(curve_shape, param)
    cmds.xform(tgt_grp, ws=True, t=init_pos)

    poci = cmds.createNode("pointOnCurveInfo", name="poci_{}".format(label))
    cmds.setAttr("{}.turnOnPercentage".format(poci), False)
    cmds.setAttr("{}.parameter".format(poci), param)
    cmds.connectAttr("{}.worldSpace[0]".format(curve_shape),
                     "{}.inputCurve".format(poci))

    cmds.connectAttr("{}.position".format(poci), "{}.translate".format(tgt_grp))

    _, dcm = _build_orient_network(poci, label)
    cmds.connectAttr("{}.outputRotate".format(dcm), "{}.rotate".format(tgt_grp))

    return tgt_grp


def _build_bind_joint_pair(center_node, tgt_grp, label, parent_grp):
    ctr_pos  = cmds.xform(center_node, q=True, ws=True, t=True)
    bind_pos = cmds.xform(tgt_grp,     q=True, ws=True, t=True)

    # offset group sits at center – its worldMatrix is the cycle-free input
    off_ctr = cmds.group(em=True, name="off_ctr_{}".format(label))
    cmds.xform(off_ctr, ws=True, t=ctr_pos)
    cmds.parent(off_ctr, parent_grp)

    cmds.select(cl=True)
    ctr_jnt = cmds.joint(name="jnt_ctr_{}".format(label))
    cmds.xform(ctr_jnt, ws=True, t=ctr_pos)
    cmds.parent(ctr_jnt, off_ctr)
    cmds.setAttr("{}.translate".format(ctr_jnt), 0, 0, 0)
    cmds.setAttr("{}.rotate".format(ctr_jnt),    0, 0, 0)
    _set_color(ctr_jnt, COLOR_BLUE)

    cmds.select(cl=True)
    bind_jnt = cmds.joint(name="jnt_bind_{}".format(label))
    cmds.xform(bind_jnt, ws=True, t=bind_pos)
    cmds.parent(bind_jnt, ctr_jnt)
    _set_color(bind_jnt, COLOR_YELLOW)

    cmds.joint(ctr_jnt, e=True, oj="xyz", sao="yup", ch=True, zso=True)

    aim = cmds.createNode("aimMatrix", name="aimMtx_{}".format(label))
    cmds.setAttr("{}.primaryInputAxisX".format(aim),   1)
    cmds.setAttr("{}.primaryInputAxisY".format(aim),   0)
    cmds.setAttr("{}.primaryInputAxisZ".format(aim),   0)
    cmds.setAttr("{}.secondaryInputAxisX".format(aim), 0)
    cmds.setAttr("{}.secondaryInputAxisY".format(aim), 1)
    cmds.setAttr("{}.secondaryInputAxisZ".format(aim), 0)
    cmds.setAttr("{}.primaryMode".format(aim),   1)
    cmds.setAttr("{}.secondaryMode".format(aim), 1)

    # off_ctr.worldMatrix → inputMatrix (never reads ctr_jnt itself → no cycle)
    cmds.connectAttr("{}.worldMatrix[0]".format(off_ctr),
                     "{}.inputMatrix".format(aim))
    cmds.connectAttr("{}.worldMatrix[0]".format(tgt_grp),
                     "{}.primaryTargetMatrix".format(aim))

    aim_dcm = cmds.createNode("decomposeMatrix", name="decMtx_aim_{}".format(label))
    cmds.connectAttr("{}.outputMatrix".format(aim),   "{}.inputMatrix".format(aim_dcm))
    cmds.connectAttr("{}.outputRotate".format(aim_dcm), "{}.rotate".format(ctr_jnt))

    cmds.setAttr("{}.jointOrientX".format(ctr_jnt), 0)
    cmds.setAttr("{}.jointOrientY".format(ctr_jnt), 0)
    cmds.setAttr("{}.jointOrientZ".format(ctr_jnt), 0)

    cmds.select(cl=True)
    return ctr_jnt, bind_jnt


# ─────────────────────────────────────────────────────────────────────────────
#  CORE BUILD
# ─────────────────────────────────────────────────────────────────────────────

def build_curve_system(curve_transform, center_node, num_mid, num_bind,
                       skip_end_drivers=False, extra_lo_joints=None):
    base = curve_transform

    root_grp      = cmds.group(em=True, name="{}_GRP".format(base))
    curves_grp    = cmds.group(em=True, name="{}_curves_GRP".format(base),    parent=root_grp)
    drivers_grp   = cmds.group(em=True, name="{}_drivers_GRP".format(base),   parent=root_grp)
    bind_jnts_grp = cmds.group(em=True, name="{}_bindJoints_GRP".format(base), parent=root_grp)

    lo_name  = "{}_lo".format(base)
    lo_curve = cmds.rename(curve_transform, lo_name)
    lo_curve = _rebuild_curve(lo_curve, LO_SPANS, lo_name)
    lo_shape = _get_curve_shape(lo_curve)

    mid_name  = "{}_mid".format(base)
    mid_curve = cmds.duplicate(lo_curve, name=mid_name)[0]
    cmds.delete(mid_curve, ch=True)
    mid_curve = _rebuild_curve(mid_curve, MID_SPANS, mid_name)
    mid_shape = _get_curve_shape(mid_curve)

    cmds.parent(lo_curve,  curves_grp)
    cmds.parent(mid_curve, curves_grp)

    if skip_end_drivers:
        if extra_lo_joints is None or len(extra_lo_joints) != 2:
            raise ValueError("skip_end_drivers=True requires extra_lo_joints=[start, end].")
        mid_param   = float(LO_SPANS) / 2.0
        label_mid   = "{}_lo_2".format(base)
        _, mid_jnt  = _build_driver_joint(lo_shape, mid_param, label_mid,
                                          drivers_grp, COLOR_RED)
        lo_joints_created = [mid_jnt]
        full_lo_joints    = [extra_lo_joints[0], mid_jnt, extra_lo_joints[1]]
    else:
        lo_params         = [0.0, float(LO_SPANS) / 2.0, float(LO_SPANS)]
        lo_joints_created = []
        for idx, param in enumerate(lo_params):
            label = "{}_lo_{}".format(base, idx + 1)
            _, jnt = _build_driver_joint(lo_shape, param, label,
                                         drivers_grp, COLOR_RED)
            lo_joints_created.append(jnt)
        full_lo_joints = lo_joints_created

    cmds.skinCluster(
        full_lo_joints + [lo_curve],
        name="sc_{}_lo".format(base),
        toSelectedBones=True, skinMethod=0, normalizeWeights=1,
    )

    mid_driver_joints = []
    for idx, param in enumerate(MID_PARAMS[num_mid]):
        label    = "{}_mid_{}".format(base, idx + 1)
        off, jnt = _build_driver_joint(lo_shape, param, label,
                                       drivers_grp, COLOR_ORANGE)

        poci = cmds.createNode("pointOnCurveInfo", name="poci_{}".format(label))
        cmds.setAttr("{}.turnOnPercentage".format(poci), False)
        cmds.setAttr("{}.parameter".format(poci), param)
        cmds.connectAttr("{}.worldSpace[0]".format(lo_shape),
                         "{}.inputCurve".format(poci))

        cmds.connectAttr("{}.position".format(poci), "{}.translate".format(off))

        _, dcm = _build_orient_network(poci, label)
        cmds.connectAttr("{}.outputRotate".format(dcm), "{}.rotate".format(off))

        mid_driver_joints.append(jnt)

    cmds.skinCluster(
        full_lo_joints + mid_driver_joints + [mid_curve],
        name="sc_{}_mid".format(base),
        toSelectedBones=True, skinMethod=0, normalizeWeights=1,
    )

    if num_bind == 1:
        bind_params = [float(MID_SPANS) / 2.0]
    else:
        step        = float(MID_SPANS) / (num_bind - 1)
        bind_params = [i * step for i in range(num_bind)]

    bind_joints = []
    for idx, param in enumerate(bind_params):
        label    = "{}_bind_{}".format(base, idx + 1)
        tgt      = _build_target_group(mid_shape, param, label)
        cmds.parent(tgt, drivers_grp)
        ctr_jnt, bind_jnt = _build_bind_joint_pair(center_node, tgt, label,
                                                    bind_jnts_grp)
        bind_joints.append(bind_jnt)

    print("[CCD] Built: {}  |  lo: {}  mid: {}  bind: {}".format(
        base, full_lo_joints, mid_driver_joints, bind_joints))

    return {
        "root_grp":          root_grp,
        "lo_curve":          lo_curve,
        "mid_curve":         mid_curve,
        "lo_joints":         full_lo_joints,
        "lo_joints_created": lo_joints_created,
        "mid_driver_joints": mid_driver_joints,
        "bind_joints":       bind_joints,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  UI
# ─────────────────────────────────────────────────────────────────────────────

WINDOW_NAME  = "cartoonCurveDeformerWin"
WINDOW_TITLE = "Cartoon Curve Deformer"

# colours (normalised 0-1)
_C = {
    "bg":        (0.165, 0.165, 0.165),   # window background
    "panel":     (0.21,  0.21,  0.21 ),   # section card
    "row":       (0.19,  0.19,  0.19 ),   # alternating row tint
    "accent":    (0.18,  0.52,  0.38 ),   # green BUILD button
    "accent_hi": (0.22,  0.72,  0.54 ),   # hover approximation (unused at runtime)
    "tag_none":  (0.28,  0.28,  0.28 ),   # pill when empty
    "tag_set":   (0.16,  0.38,  0.28 ),   # pill when filled
    "btn":       (0.30,  0.30,  0.30 ),   # normal button face
    "sep":       (0.13,  0.13,  0.13 ),   # hard separator line
}

_state = {
    "curve1":     None,
    "curve2":     None,
    "center":     None,
    "use_curve2": False,
}

# UI control references that need cross-function access
_ui = {}


def _pill_text(key):
    """Return short display label for a state key."""
    v = _state[key]
    return v if v else "—"


def _refresh_pill(key):
    ctrl = _ui.get("pill_" + key)
    if ctrl is None:
        return
    v    = _state[key]
    text = v if v else "—"
    bg   = _C["tag_set"] if v else _C["tag_none"]
    cmds.text(ctrl, e=True, label=text, backgroundColor=bg)


def _pick_curve(key):
    sel = cmds.ls(sl=True, type="transform")
    if not sel:
        cmds.warning("Select a curve transform first.")
        return
    if not (cmds.listRelatives(sel[0], shapes=True, type="nurbsCurve") or []):
        cmds.warning("{} has no nurbsCurve shape.".format(sel[0]))
        return
    _state[key] = sel[0]
    _refresh_pill(key)


def _pick_center():
    sel = cmds.ls(sl=True, type="transform")
    if not sel:
        cmds.warning("Select a locator, joint, or group as the center.")
        return
    _state["center"] = sel[0]
    _refresh_pill("center")


def _toggle_curve2(value):
    _state["use_curve2"] = value
    enabled = bool(value)
    cmds.text(   _ui["pill_curve2"],   e=True, enable=enabled)
    cmds.button( _ui["btn_curve2"],    e=True, enable=enabled)
    if not enabled:
        _state["curve2"] = None
        _refresh_pill("curve2")


def _on_build(mid_menu, bind_menu):
    num_mid  = int(cmds.optionMenu(mid_menu,  q=True, v=True))
    num_bind = int(cmds.optionMenu(bind_menu, q=True, v=True))

    curve1  = _state["curve1"]
    curve2  = _state["curve2"] if _state["use_curve2"] else None
    center  = _state["center"]

    # ── validation ────────────────────────────────────────────────────────────
    errors = []
    if not curve1:                          errors.append("First Curve not set.")
    elif not cmds.objExists(curve1):        errors.append("First Curve no longer exists.")
    if not center:                          errors.append("Center Node not set.")
    elif not cmds.objExists(center):        errors.append("Center Node no longer exists.")
    if _state["use_curve2"]:
        if not curve2:                      errors.append("Second Curve enabled but not set.")
        elif not cmds.objExists(curve2):    errors.append("Second Curve no longer exists.")
    if errors:
        cmds.confirmDialog(title="Build Error",
                           message="\n".join(errors),
                           button=["OK"], defaultButton="OK")
        return

    # ── build ─────────────────────────────────────────────────────────────────
    try:
        result1 = build_curve_system(curve1, center, num_mid, num_bind,
                                     skip_end_drivers=False)
        if curve2:
            lo_full = result1["lo_joints"]
            build_curve_system(curve2, center, num_mid, num_bind,
                               skip_end_drivers=True,
                               extra_lo_joints=[lo_full[0], lo_full[-1]])

        cmds.inViewMessage(
            amg="<b>Cartoon Curve Deformer</b> — built successfully.",
            pos="topCenter", fade=True,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        cmds.confirmDialog(title="Build Failed",
                           message=str(e),
                           button=["OK"], defaultButton="OK")
        return

    # reset state
    for k in ("curve1", "curve2"):
        _state[k] = None
        _refresh_pill(k)


# ── reusable row builder ──────────────────────────────────────────────────────

def _picker_row(label, pill_key, btn_key, command, enabled=True):
    """
    One labelled pick row:
      [label text]  [────── name pill ──────]  [Pick ▸]
    Stores pill and button references in _ui.
    """
    cmds.rowLayout(
        numberOfColumns=3,
        columnWidth3=(100, 200, 56),
        columnAlign3=("right", "center", "center"),
        columnAttach3=("right", "both", "left"),
        height=28,
    )
    cmds.text(label=label, align="right",
              font="smallBoldLabelFont",
              backgroundColor=_C["panel"])

    pill = cmds.text(
        label=_pill_text(pill_key),
        align="center",
        height=22,
        backgroundColor=_C["tag_none"] if not _state[pill_key] else _C["tag_set"],
        enable=enabled,
    )
    _ui["pill_" + pill_key] = pill

    btn = cmds.button(
        label="Pick",
        width=52, height=22,
        backgroundColor=_C["btn"],
        command=command,
        enable=enabled,
    )
    if btn_key:
        _ui[btn_key] = btn

    cmds.setParent("..")


def _section(title):
    """Thin titled separator."""
    cmds.separator(h=10, style="none")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(12, 350), adjustableColumn=2)
    cmds.text(label="", width=12)
    cmds.text(label=title.upper(),
              align="left",
              font="tinyBoldLabelFont",
              backgroundColor=_C["bg"])
    cmds.setParent("..")
    cmds.separator(h=1, style="in")


def _card(content_fn):
    """Raised card panel."""
    cmds.frameLayout(
        labelVisible=False,
        borderStyle="etchedIn",
        backgroundColor=_C["panel"],
        marginWidth=8,
        marginHeight=6,
    )
    content_fn()
    cmds.setParent("..")


# ── main window ───────────────────────────────────────────────────────────────

def show_ui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    win = cmds.window(
        WINDOW_NAME,
        title=WINDOW_TITLE,
        widthHeight=(420, 1),
        sizeable=False,
        resizeToFitChildren=True,
        backgroundColor=_C["bg"],
    )

    cmds.columnLayout(
        adjustableColumn=True,
        rowSpacing=0,
        columnOffset=("both", 12),
        backgroundColor=_C["bg"],
    )

    # ── header ────────────────────────────────────────────────────────────────
    cmds.separator(h=14, style="none")
    cmds.text(
        label="CARTOON CURVE DEFORMER",
        align="center",
        font="boldLabelFont",
        height=22,
        backgroundColor=_C["bg"],
    )
    cmds.text(
        label="Matrix based curve deformation system",
        align="center",
        font="smallPlainLabelFont",
        height=16,
        backgroundColor=_C["bg"],
    )
    cmds.separator(h=10, style="none")

    # ── CURVES section ────────────────────────────────────────────────────────
    _section("Curves")

    def _curves_content():
        _picker_row("First Curve",  "curve1", None,
                    command=lambda *_: _pick_curve("curve1"))

        # checkbox row
        cmds.separator(h=4, style="none")
        cmds.rowLayout(numberOfColumns=2, columnWidth2=(108, 260), height=22)
        cmds.text(label="", width=108, backgroundColor=_C["bg"])
        cb = cmds.checkBox(
            label="Enable second curve",
            value=False,
            backgroundColor=_C["bg"],
            changeCommand=lambda v, *_: _toggle_curve2(v),
        )
        _ui["cb_curve2"] = cb
        cmds.setParent("..")
        cmds.separator(h=4, style="none")

        _picker_row("Second Curve", "curve2", "btn_curve2",
                    command=lambda *_: _pick_curve("curve2"),
                    enabled=False)

    _card(_curves_content)

    # ── CENTER section ────────────────────────────────────────────────────────
    _section("Center Node")

    def _center_content():
        _picker_row("Center", "center", None,
                    command=lambda *_: _pick_center())

    _card(_center_content)

    # ── SETTINGS section ──────────────────────────────────────────────────────
    _section("Settings")

    mid_menu_ref  = [None]
    bind_menu_ref = [None]

    def _settings_content():
        cmds.rowLayout(
            numberOfColumns=4,
            columnWidth4=(100, 90, 100, 90),
            columnAlign4=("right", "left", "right", "left"),
            height=28,
        )
        cmds.text(label="Mid Drivers", align="right",
                  font="smallBoldLabelFont",
                  backgroundColor=_C["bg"])
        mid_menu = cmds.optionMenu(width=72, backgroundColor=_C["btn"])
        for v in ["2", "4", "6"]:
            cmds.menuItem(label=v)
        mid_menu_ref[0] = mid_menu

        cmds.text(label="  Bind Joints", align="right",
                  font="smallBoldLabelFont",
                  backgroundColor=_C["bg"])
        bind_menu = cmds.optionMenu(width=72, backgroundColor=_C["btn"])
        for v in ["3", "5", "7", "9"]:
            cmds.menuItem(label=v)
        bind_menu_ref[0] = bind_menu

        cmds.setParent("..")

    _card(_settings_content)

    # ── BUILD button ──────────────────────────────────────────────────────────
    cmds.separator(h=12, style="none")
    cmds.button(
        label="BUILD",
        height=40,
        backgroundColor=_C["accent"],
        command=lambda *_: _on_build(mid_menu_ref[0], bind_menu_ref[0]),
    )
    
    cmds.text(label="Made by Marc-adrien LE PAPE", align="center",
                  font="smallBoldLabelFont",
                  backgroundColor=_C["bg"])

    cmds.showWindow(win)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────
show_ui()
