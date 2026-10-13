from collections import deque
from .validation import cycles


def ancestors(person, parents):
    distances = {person: 0}
    queue = deque([person])
    while queue:
        node = queue.popleft()
        for parent in sorted(parents[node]):
            if parent not in distances:
                distances[parent] = distances[node] + 1
                queue.append(parent)
    return distances


def ordinal(n):
    if n == 1:
        return "first"
    if n == 2:
        return "second"
    if n == 3:
        return "third"
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def blood(a, b, parents):
    left, right = ancestors(a, parents), ancestors(b, parents)
    shared = left.keys() & right.keys()
    if not shared:
        return None
    ancestor = min(shared, key=lambda p: (max(left[p], right[p]), left[p] + right[p], p))
    x, y = left[ancestor], right[ancestor]
    if x == 0:
        return "parent" if y == 1 else "great-" * (y - 2) + "grandparent"
    if y == 0:
        return "child" if x == 1 else "great-" * (x - 2) + "grandchild"
    if x == y == 1:
        common = parents[a] & parents[b]
        half = len(common) == 1 and bool(parents[a] - common) and bool(parents[b] - common)
        return "half-sibling" if half else "sibling"
    if x == 1:
        return "great-" * (y - 2) + "aunt/uncle"
    if y == 1:
        return "great-" * (x - 2) + "niece/nephew"
    degree, removed = min(x, y) - 1, abs(x - y)
    result = ordinal(degree) + " cousin"
    if removed:
        result += " " + ({1: "once", 2: "twice"}.get(removed, f"{removed} times")) + " removed"
    return result


def relate(tree, id1, id2):
    """Return id1's relationship to id2; one deterministic closest path."""
    a, b = (pid if pid.startswith("@") else f"@{pid}@" for pid in (id1, id2))
    for pid in (a, b):
        if pid not in tree.people:
            raise ValueError(f"Unknown individual: {pid}")
    parents = tree.parents()
    if next(cycles(parents), None) is not None:
        raise ValueError("Circular ancestry: validate and repair the tree before calculating relationships")
    if a == b:
        return "self"
    spouses = {pid: set() for pid in tree.people}
    for fam in tree.families.values():
        for pid in fam.spouses:
            spouses[pid].update(set(fam.spouses) - {pid})
    if b in spouses[a]:
        return "spouse"
    result = blood(a, b, parents)
    if result:
        return result
    labels = {"parent": "parent-in-law", "child": "child-in-law", "sibling": "sibling-in-law", "half-sibling": "sibling-in-law"}
    for spouse in sorted(spouses[b]):
        result = blood(a, spouse, parents)
        if result in labels:
            return labels[result]
    for spouse in sorted(spouses[a]):
        result = blood(spouse, b, parents)
        if result in labels:
            return labels[result]
    return "no known relationship"
