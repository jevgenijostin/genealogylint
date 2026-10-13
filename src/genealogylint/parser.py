"""Strict line structure, deliberately limited GEDCOM semantics."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from .dates import DateRange, parse_date


@dataclass
class Person:
    id: str
    name: str = ""
    sex: str = "U"
    birth: DateRange | None = None
    death: DateRange | None = None


@dataclass
class Family:
    id: str
    spouses: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    marriage: DateRange | None = None


@dataclass
class Tree:
    people: dict[str, Person] = field(default_factory=dict)
    families: dict[str, Family] = field(default_factory=dict)
    memberships: list[tuple[str, str, str]] = field(default_factory=list)

    def parents(self):
        result = {pid: set() for pid in self.people}
        for fam in self.families.values():
            for child in fam.children:
                result[child].update(fam.spouses)
        return result


def parse(text: str) -> Tree:
    tree = Tree()
    stack = []
    record = None
    seen = set()
    assigned = set()
    for number, raw in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        if not raw.strip():
            continue
        match = re.fullmatch(r"(\d+)\s+(?:(@[^@\s]+@)\s+)?([A-Za-z0-9_]+)(?:\s+(.*))?", raw)
        if not match:
            raise ValueError(f"Line {number}: malformed GEDCOM line")
        level, xref, tag, value = match.groups()
        level, tag, value = int(level), tag.upper(), (value or "").strip()
        if level > len(stack):
            raise ValueError(f"Line {number}: skipped level")
        stack = stack[:level]
        parent = stack[-1] if stack else None
        stack.append(tag)
        if xref:
            if level != 0 or xref in seen:
                raise ValueError(f"Line {number}: duplicate or nested ID {xref}")
            seen.add(xref)
        if level == 0:
            record = None
            if tag in ("INDI", "FAM"):
                if not xref:
                    raise ValueError(f"Line {number}: {tag} needs an ID")
                record = Person(xref) if tag == "INDI" else Family(xref)
                (tree.people if tag == "INDI" else tree.families)[xref] = record
            continue
        if record is None:
            continue
        field_name = None
        parsed_value = value
        if isinstance(record, Person) and level == 1 and tag in ("NAME", "SEX"):
            field_name = tag.lower()
            parsed_value = " ".join(value.replace("/", " ").split()) if tag == "NAME" else value.upper()
        elif isinstance(record, Person) and level == 1 and tag in ("FAMC", "FAMS"):
            tree.memberships.append((record.id, tag, value))
        elif isinstance(record, Family) and level == 1 and tag in ("HUSB", "WIFE", "CHIL"):
            if not re.fullmatch(r"@[^@\s]+@", value):
                raise ValueError(f"Line {number}: invalid reference {value}")
            target = record.children if tag == "CHIL" else record.spouses
            if value not in target:
                target.append(value)
        elif level == 2 and tag == "DATE":
            fields = {"BIRT": "birth", "DEAT": "death"} if isinstance(record, Person) else {"MARR": "marriage"}
            field_name = fields.get(parent)
            if field_name:
                try:
                    parsed_value = parse_date(value)
                except (ValueError, OverflowError) as exc:
                    raise ValueError(f"Line {number}: invalid or unsupported date {value!r}") from exc
        if field_name:
            key = (record.id, field_name)
            if key in assigned:
                raise ValueError(f"Line {number}: repeated {field_name} for {record.id}")
            assigned.add(key)
            setattr(record, field_name, parsed_value)
    for fam in tree.families.values():
        if len(fam.spouses) > 2:
            raise ValueError(f"{fam.id}: more than two spouses unsupported")
        for pid in fam.spouses + fam.children:
            if pid not in tree.people:
                raise ValueError(f"{fam.id}: missing individual {pid}")
    for pid, tag, fid in tree.memberships:
        if fid not in tree.families:
            raise ValueError(f"{pid}: missing family {fid}")
        fam = tree.families[fid]
        if pid not in (fam.children if tag == "FAMC" else fam.spouses):
            raise ValueError(f"{pid}: {tag} {fid} is not reciprocated in the family record")
    return tree


def load(path):
    return parse(Path(path).read_text(encoding="utf-8-sig"))
