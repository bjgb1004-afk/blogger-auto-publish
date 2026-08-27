import register_tasks


def test_build_schtasks_commands():
    cmds = register_tasks.build_schtasks_commands(python_exe="C:\\py\\python.exe")
    assert len(cmds) == 2
    gen_cmd, chk_cmd = cmds
    assert "generate_drafts.py" in " ".join(gen_cmd)
    assert "hourly" in gen_cmd
    assert "2" in gen_cmd
    assert "check_approvals.py" in " ".join(chk_cmd)
    assert "minute" in chk_cmd
    assert "10" in chk_cmd
