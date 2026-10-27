"""固定角色预算防止前面的调查耗尽反证与复核额度。"""
def allocate_role_budget(total, roles=("A1", "A2", "A3", "A4", "A5")):
    limits = {role: 0 for role in roles}
    priority = [r for r in ("A5", "A4", "A1", "A2", "A3") if r in roles]
    remaining = total
    for role in priority:
        if remaining:
            limits[role] += 1
            remaining -= 1
    targets = {"A1": 3, "A2": 4, "A3": 4, "A4": 4, "A5": 5}
    while remaining:
        changed = False
        for role in priority:
            if remaining and (limits[role] < targets[role] or len(roles) < 5):
                limits[role] += 1
                remaining -= 1
                changed = True
        if not changed:
            break
    return limits
