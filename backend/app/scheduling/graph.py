from collections import defaultdict, deque

from app.scheduling.errors import ScheduleError


def topological_order(task_ids, dependencies) -> list[int]:
    task_ids = list(task_ids)
    known = set(task_ids)
    outgoing = defaultdict(list)
    indegree = {task_id: 0 for task_id in task_ids}

    for dependency in dependencies:
        predecessor = dependency.predecessor_task_id
        successor = dependency.successor_task_id
        if predecessor not in known or successor not in known:
            raise ScheduleError(
                "invalid_dependency",
                "Dependencies must connect tasks in this project.",
                422,
            )
        if predecessor == successor:
            raise ScheduleError(
                "self_dependency",
                "A task cannot depend on itself.",
                422,
            )
        outgoing[predecessor].append(successor)
        indegree[successor] += 1

    ready = deque(task_id for task_id in task_ids if indegree[task_id] == 0)
    order = []
    while ready:
        task_id = ready.popleft()
        order.append(task_id)
        for successor in outgoing[task_id]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)

    if len(order) != len(task_ids):
        raise ScheduleError(
            "dependency_cycle",
            "The project dependencies contain a cycle.",
            422,
        )
    return order
