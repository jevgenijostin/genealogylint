from dataclasses import asdict, dataclass
from .dates import age, before


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    ids: tuple[str, ...]
    message: str

    def to_dict(self):
        return asdict(self)


def cycles(parents):
    """Iterative DFS: report deterministic back-edge cycle witnesses."""
    done, active, path = set(), {}, []
    for root in sorted(parents):
        if root in done:
            continue
        work = [(root, False)]
        while work:
            node, leaving = work.pop()
            if leaving:
                active.pop(node)
                path.pop()
                done.add(node)
            elif node in active:
                yield tuple(path[active[node]:] + [node])
            elif node not in done:
                active[node] = len(path)
                path.append(node)
                work.append((node, True))
                work.extend((p, False) for p in sorted(parents[node], reverse=True))


def validate(tree, min_parent_age=12, max_parent_age=75, max_death_age=120):
    if not 0 <= min_parent_age <= max_parent_age or max_death_age < 0:
        raise ValueError("Age thresholds must be nonnegative and minimum <= maximum")
    findings = []
    def add(severity, code, ids, message):
        findings.append(Finding(severity, code, tuple(ids), message))
    parents = tree.parents()
    for cycle in cycles(parents):
        add("ERROR", "circular_ancestry", cycle, "Ancestry cycle: " + " -> ".join(cycle))
    linked = set()
    for fam in tree.families.values():
        linked.update(fam.spouses + fam.children)
        for pid in fam.spouses:
            person = tree.people[pid]
            if before(fam.marriage, person.birth):
                add("ERROR", "marriage_before_birth", (fam.id, pid), "Marriage precedes spouse's birth")
            if before(person.death, fam.marriage):
                add("ERROR", "marriage_after_death", (fam.id, pid), "Marriage follows spouse's death")
    duplicates = {}
    for pid, person in tree.people.items():
        if before(person.death, person.birth):
            add("ERROR", "death_before_birth", (pid,), "Death precedes birth")
        if person.birth and person.death and person.birth.upper and person.death.lower:
            if age(person.birth.upper, person.death.lower) > max_death_age:
                add("WARNING", "death_age", (pid,), f"Age at death exceeds {max_death_age}")
        for parent in sorted(parents[pid]):
            birth = tree.people[parent].birth
            child = person.birth
            if not birth or not child:
                continue
            young = birth.lower and child.upper and age(birth.lower, child.upper) < min_parent_age
            old = birth.upper and child.lower and age(birth.upper, child.lower) > max_parent_age
            if young or old:
                add("WARNING", "parent_age", (parent, pid), f"Parent age outside {min_parent_age}..{max_parent_age} years")
        if person.name:
            key = (person.name.casefold(), person.birth.text if person.birth else None)
            duplicates.setdefault(key, []).append(pid)
        if pid not in linked:
            add("INFO", "orphan", (pid,), "Individual is not referenced by any family")
    for ids in duplicates.values():
        if len(ids) > 1:
            add("WARNING", "possible_duplicate", sorted(ids), "Same full name and birth date (or both dates missing)")
    ranks = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    return sorted(findings, key=lambda f: (ranks[f.severity], f.code, f.ids))
