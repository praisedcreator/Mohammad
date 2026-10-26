from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from cost_report import ROOT,build_report,load_budgets,load_costs,money


class CostTests(unittest.TestCase):
    def setUp(self):
        test_root=(ROOT/'.runtime/tests').resolve();test_root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='portfolio-costs-',dir=test_root)
        if not Path(self.temp.name).resolve().is_relative_to(test_root):raise RuntimeError('Test cleanup must remain inside the project')
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'costs.csv'

    def csv(self,body):
        self.path.write_text('record_id,date,provider,service,environment,currency,cost\n'+body,encoding='utf-8')
        return load_costs(self.path)

    def test_sample_provider_totals_and_thresholds(self):
        result=build_report(load_costs(ROOT/'sample-costs.csv'),load_budgets(ROOT/'budgets.json'))
        reports={r['provider']:r for r in result['monthly_reports']}
        self.assertEqual(reports['aws']['spend'],'433.75')
        self.assertEqual(reports['azure']['status'],'OVER_BUDGET')
        self.assertEqual(reports['aws']['status'],'APPROACHING_BUDGET')

    def test_decimal_sum_is_exact(self):
        rows=self.csv('one,2026-09-01,aws,S3,dev,USD,0.10\ntwo,2026-09-02,aws,S3,dev,USD,0.20\n')
        self.assertEqual(build_report(rows,{'aws':Decimal('1')})['monthly_reports'][0]['spend'],'0.30')

    def test_80_percent_boundary(self):
        rows=self.csv('one,2026-09-01,aws,S3,dev,USD,80.00\n')
        self.assertEqual(build_report(rows,{'aws':Decimal('100')})['monthly_reports'][0]['status'],'APPROACHING_BUDGET')

    def test_rounded_percent_does_not_change_status(self):
        rows=self.csv('one,2026-09-01,aws,S3,dev,USD,7999.99\n')
        self.assertEqual(build_report(rows,{'aws':Decimal('10000')})['monthly_reports'][0]['status'],'WITHIN_BUDGET')

    def test_months_are_not_merged(self):
        rows=self.csv('one,2026-09-01,aws,S3,dev,USD,10\ntwo,2026-10-01,aws,S3,dev,USD,20\n')
        self.assertEqual(len(build_report(rows,{})['monthly_reports']),2)

    def test_missing_budget_is_explicit(self):
        rows=self.csv('one,2026-09-01,aws,S3,dev,USD,10\n')
        result=build_report(rows,{})['monthly_reports'][0]
        self.assertEqual(result['status'],'NO_BUDGET');self.assertIsNone(result['budget_used_percent'])

    def test_duplicate_records_rejected(self):
        with self.assertRaises(ValueError):self.csv('one,2026-09-01,aws,S3,dev,USD,10\none,2026-09-02,aws,S3,dev,USD,10\n')

    def test_invalid_money_rejected(self):
        for value in ['NaN','Infinity','-1','1e3','1.001','1,000',True]:
            with self.subTest(value=value),self.assertRaises(ValueError):money(value)

    def test_wrong_currency_or_provider_rejected(self):
        for provider,currency in [('aws','EUR'),('unknown','USD')]:
            with self.subTest(provider=provider,currency=currency),self.assertRaises(ValueError):
                self.csv(f'one,2026-09-01,{provider},S3,dev,{currency},10\n')

    def test_invalid_date_or_missing_fields_rejected(self):
        for row in ['one,2026-02-30,aws,S3,dev,USD,10\n','one,20260901,aws,S3,dev,USD,10\n','one,2026-09-01,aws,,dev,USD,10\n','one,2026-09-01,aws,S3,dev,USD,10,extra\n']:
            with self.subTest(row=row),self.assertRaises(ValueError):self.csv(row)

    def test_empty_input_rejected(self):
        with self.assertRaises(ValueError):self.csv('')

    def test_bad_header_rejected(self):
        self.path.write_text('wrong,header\none,two\n')
        with self.assertRaises(ValueError):load_costs(self.path)

    def test_budgets_are_positive_and_provider_scoped(self):
        for obj in [{'aws':'0'},{'unknown':'100'},{'aws':100},{}]:
            self.path.write_text(json.dumps(obj))
            with self.subTest(obj=obj),self.assertRaises(ValueError):load_budgets(self.path)

    def test_environment_totals_reconcile(self):
        report=build_report(load_costs(ROOT/'sample-costs.csv'),load_budgets(ROOT/'budgets.json'))
        for row in report['monthly_reports']:
            self.assertEqual(sum(map(Decimal,row['environment_totals'].values())),Decimal(row['spend']))


if __name__=='__main__':unittest.main()
