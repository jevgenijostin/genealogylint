import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from datetime import date

from genealogylint.cli import main
from genealogylint.dates import parse_date
from genealogylint.license import create_demo_key, enforce, is_valid_license
from genealogylint.parser import load, parse
from genealogylint.relationships import relate
from genealogylint.validation import validate

FIXTURES = Path(__file__).parent / "fixtures"


class ValidationTests(unittest.TestCase):
    def codes(self, name, **kwargs):
        return [f.code for f in validate(load(FIXTURES / (name + '.ged')), **kwargs)]

    def test_circular_ancestry(self):
        self.assertEqual(self.codes('cycle'), ['circular_ancestry'])

    def test_death_before_birth(self):
        self.assertIn('death_before_birth', self.codes('death'))

    def test_marriage_before_birth(self):
        self.assertIn('marriage_before_birth', self.codes('marriage'))

    def test_marriage_after_death(self):
        self.assertIn('marriage_after_death', self.codes('marriage'))

    def test_parent_age(self):
        self.assertEqual(self.codes('parent_age'), ['parent_age', 'parent_age'])

    def test_configurable_parent_age(self):
        self.assertEqual(self.codes('parent_age', min_parent_age=10, max_parent_age=100), [])

    def test_death_age(self):
        self.assertIn('death_age', self.codes('death_age'))

    def test_death_age_threshold(self):
        self.assertNotIn('death_age', self.codes('death_age', max_death_age=121))

    def test_duplicates(self):
        findings = [f.ids for f in validate(load(FIXTURES / 'duplicates.ged')) if f.code == 'possible_duplicate']
        self.assertEqual(findings, [('@A@', '@B@'), ('@C@', '@D@')])

    def test_orphans(self):
        findings = validate(load(FIXTURES / 'orphan.ged'))
        self.assertEqual([(f.code, f.ids) for f in findings], [('orphan', ('@C@',))])

    def test_uncertain_dates_do_not_prove_contradiction(self):
        tree = parse('0 @A@ INDI\n1 BIRT\n2 DATE ABT 1900\n1 DEAT\n2 DATE 1899')
        self.assertEqual([f.code for f in validate(tree)], ['orphan'])

    def test_invalid_thresholds(self):
        with self.assertRaises(ValueError):
            validate(parse(''), min_parent_age=76)

    def test_ranked_and_deterministic(self):
        text = (FIXTURES / 'death.ged').read_text() + '\n' + (FIXTURES / 'parent_age.ged').read_text()
        tree = parse(text)
        self.assertEqual([f.severity for f in validate(tree)], ['ERROR', 'WARNING', 'WARNING', 'INFO'])
        self.assertEqual(validate(tree), validate(tree))

    def test_self_cycle(self):
        tree = parse('0 @A@ INDI\n0 @F@ FAM\n1 HUSB @A@\n1 CHIL @A@')
        self.assertEqual(validate(tree)[0].ids, ('@A@', '@A@'))

    def test_deep_chain(self):
        text = '\n'.join(f'0 @I{i}@ INDI' for i in range(1500))
        text += '\n' + '\n'.join(f'0 @F{i}@ FAM\n1 HUSB @I{i}@\n1 CHIL @I{i+1}@' for i in range(1499))
        self.assertEqual(validate(parse(text)), [])


class RelationshipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = load(FIXTURES / 'relationships.ged')

    def test_sibling(self):
        self.assertEqual(relate(self.tree, 'A', 'B'), 'sibling')

    def test_half_sibling(self):
        self.assertEqual(relate(self.tree, 'A', 'HALF'), 'half-sibling')

    def test_parent(self):
        self.assertEqual(relate(self.tree, 'P1', 'A'), 'parent')

    def test_grandparent(self):
        self.assertEqual(relate(self.tree, 'G1', 'A'), 'grandparent')

    def test_great_grandparent(self):
        self.assertEqual(relate(self.tree, 'G1', 'D'), 'great-grandparent')

    def test_aunt_uncle(self):
        self.assertEqual(relate(self.tree, 'P2', 'A'), 'aunt/uncle')

    def test_first_cousin(self):
        self.assertEqual(relate(self.tree, 'A', 'C'), 'first cousin')

    def test_second_cousin_once_removed(self):
        self.assertEqual(relate(self.tree, 'D', 'F'), 'second cousin once removed')
        self.assertEqual(relate(self.tree, 'F', 'D'), 'second cousin once removed')

    def test_unrelated(self):
        self.assertEqual(relate(self.tree, 'A', 'UNRELATED'), 'no known relationship')

    def test_reverse_directions(self):
        for a, b, expected in [('A', 'P1', 'child'), ('A', 'G1', 'grandchild'), ('A', 'P2', 'niece/nephew')]:
            with self.subTest(expected=expected):
                self.assertEqual(relate(self.tree, a, b), expected)

    def test_in_laws(self):
        for a, b, expected in [('P1', 'PARTNER', 'parent-in-law'), ('PARTNER', 'P1', 'child-in-law'), ('B', 'PARTNER', 'sibling-in-law')]:
            with self.subTest(expected=expected):
                self.assertEqual(relate(self.tree, a, b), expected)

    def test_spouse_and_self(self):
        self.assertEqual(relate(self.tree, '@A@', '@PARTNER@'), 'spouse')
        self.assertEqual(relate(self.tree, 'A', 'A'), 'self')

    def test_unknown_id(self):
        with self.assertRaises(ValueError):
            relate(self.tree, 'MISSING', 'A')

    def test_cycles_terminate(self):
        with self.assertRaisesRegex(ValueError, 'Circular ancestry'):
            relate(load(FIXTURES / 'cycle.ged'), 'A', 'B')

    def test_pedigree_collapse_is_not_a_cycle(self):
        tree = parse('0 @A@ INDI\n0 @B@ INDI\n0 @C@ INDI\n0 @D@ INDI\n0 @F1@ FAM\n1 HUSB @A@\n1 CHIL @B@\n1 CHIL @C@\n0 @F2@ FAM\n1 HUSB @B@\n1 WIFE @C@\n1 CHIL @D@')
        self.assertEqual(validate(tree), [])
        self.assertEqual(relate(tree, 'A', 'D'), 'grandparent')


class ParserTests(unittest.TestCase):
    def test_name_sex_and_bom(self):
        person = parse('\ufeff0 @A@ INDI\n1 NAME Ada /Smith/\n1 SEX F').people['@A@']
        self.assertEqual((person.name, person.sex), ('Ada Smith', 'F'))

    def test_dates(self):
        cases = [('1900', date(1900, 1, 1), date(1900, 12, 31)), ('FEB 2000', date(2000, 2, 1), date(2000, 2, 29)), ('1 JAN 1900', date(1900, 1, 1), date(1900, 1, 1)), ('BEF 1900', None, date(1899, 12, 31)), ('AFT 1900', date(1901, 1, 1), None), ('ABT 1900', date(1899, 1, 1), date(1901, 12, 31)), ('BET 1900 AND 1902', date(1900, 1, 1), date(1902, 12, 31))]
        for value, low, high in cases:
            with self.subTest(value=value):
                actual = parse_date(value)
                self.assertEqual((actual.lower, actual.upper), (low, high))

    def test_bad_dates(self):
        for value in ['31 FEB 1900', 'BET 2000 AND 1900', 'BET 1900', '@#DJULIAN@ 1900', 'CAL 1900', '0000']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_date(value)

    def test_bad_structure(self):
        for text in ['hello', '1 NAME Ada', '0 @A@ INDI\n2 DATE 1900', '0 INDI', '0 @A@ INDI\n0 @A@ INDI', '0 @F@ FAM\n1 CHIL @MISSING@', '0 @A@ INDI\n1 BIRT\n2 DATE 1900\n2 DATE 1901']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse(text)

    def test_unknown_tags_ignored(self):
        self.assertEqual(len(parse('0 @A@ INDI\n1 NOTE private\n2 CONT note').people), 1)

    def test_reciprocal_family_pointers(self):
        tree = parse('0 @A@ INDI\n1 FAMS @F@\n0 @B@ INDI\n1 FAMC @F@\n0 @F@ FAM\n1 HUSB @A@\n1 CHIL @B@')
        self.assertEqual(validate(tree), [])
        for text in ['0 @A@ INDI\n1 FAMC @F@', '0 @A@ INDI\n1 FAMS @F@\n0 @F@ FAM']:
            with self.assertRaises(ValueError):
                parse(text)


class CliAndLicenseTests(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_license_checksum(self):
        key = create_demo_key()
        self.assertTrue(is_valid_license(key.lower()))
        self.assertFalse(is_valid_license(key[:-1] + ('0' if key[-1] != '0' else '1')))
        self.assertFalse(is_valid_license(''))

    def test_license_limits(self):
        enforce(100, '')
        with self.assertRaises(ValueError):
            enforce(101, '')
        with self.assertRaises(ValueError):
            enforce(1, '', batch=True)
        enforce(101, create_demo_key(), batch=True)

    def test_validate_json(self):
        code, out, err = self.run_cli('validate', str(FIXTURES / 'death.ged'), '--json')
        self.assertEqual((code, err), (1, ''))
        self.assertEqual(json.loads(out)['findings'][0]['code'], 'death_before_birth')

    def test_human_and_relate(self):
        self.assertIn('SEVERITY', self.run_cli('validate', str(FIXTURES / 'orphan.ged'))[1])
        self.assertEqual(self.run_cli('relate', str(FIXTURES / 'relationships.ged'), 'A', 'C'), (0, 'first cousin\n', ''))

    def test_batch(self):
        file = str(FIXTURES / 'orphan.ged')
        code, out, _ = self.run_cli('validate', file, file, '--batch', '--json', '--license-key', create_demo_key())
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), 2)
        self.assertEqual(self.run_cli('validate', file, file)[0], 2)
        self.assertEqual(self.run_cli('validate', file, '--batch', '--license-key', '')[0], 2)

    def test_errors_leave_stdout_clean(self):
        code, out, err = self.run_cli('validate', 'missing.ged', '--json')
        self.assertEqual((code, out), (2, ''))
        self.assertTrue(err)

    def test_cli_large_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'large.ged'
            path.write_text('\n'.join(f'0 @I{i}@ INDI' for i in range(101)), encoding='utf-8')
            self.assertEqual(self.run_cli('validate', str(path), '--license-key', '')[0], 2)
            self.assertEqual(self.run_cli('validate', str(path), '--license-key', create_demo_key())[0], 0)


if __name__ == '__main__':
    unittest.main()
