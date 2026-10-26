"""Summarize practice cloud billing CSV files with exact decimal arithmetic."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parent
COLUMNS=['record_id','date','provider','service','environment','currency','cost']
PROVIDERS={'aws','azure','gcp'}


def money(value,positive=False):
    if not isinstance(value,str) or not re.fullmatch(r'(0|[1-9][0-9]{0,14})(\.[0-9]{1,2})?',value):
        raise ValueError('Amounts must be nonnegative decimal strings with at most two fraction digits.')
    amount=Decimal(value)
    if positive and amount<=0:raise ValueError('Budgets must be greater than zero.')
    return amount


def load_budgets(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data,dict) or not data:raise ValueError('Provide a nonempty provider-to-monthly-budget object.')
    if set(data)-PROVIDERS:raise ValueError('Unknown budget provider.')
    return {provider:money(value,positive=True) for provider,value in data.items()}


def load_costs(path):
    rows=[];seen=set()
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=COLUMNS:raise ValueError('CSV columns must match the documented schema and order.')
        for line,row in enumerate(reader,2):
            if set(row)!=set(COLUMNS) or any(v is None or not v.strip() for v in row.values()):
                raise ValueError(f'Missing or extra CSV fields at line {line}.')
            row={k:v.strip() for k,v in row.items()}
            provider=row['provider'].lower()
            if provider not in PROVIDERS:raise ValueError(f'Unknown provider at line {line}.')
            if row['currency']!='USD':raise ValueError('This lab supports USD only; convert or separate currencies before use.')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',row['date']):raise ValueError('Dates must use YYYY-MM-DD.')
            date.fromisoformat(row['date'])
            identity=(provider,row['record_id'])
            if identity in seen:raise ValueError(f'Duplicate billing record at line {line}.')
            seen.add(identity)
            row.update(provider=provider,amount=money(row['cost']))
            rows.append(row)
    if not rows:raise ValueError('The input contains no billing records.')
    return rows


def build_report(rows,budgets):
    groups=defaultdict(list)
    for row in rows:groups[(row['date'][:7],row['provider'])].append(row)
    reports=[]
    for (month,provider),records in sorted(groups.items()):
        total=sum((r['amount'] for r in records),Decimal('0'))
        budget=budgets.get(provider)
        ratio=total/budget if budget else None
        status='NO_BUDGET' if budget is None else 'OVER_BUDGET' if total>budget else 'APPROACHING_BUDGET' if ratio>=Decimal('0.8') else 'WITHIN_BUDGET'
        services=defaultdict(lambda:Decimal('0'))
        environments=defaultdict(lambda:Decimal('0'))
        for row in records:
            services[row['service']]+=row['amount']
            environments[row['environment']]+=row['amount']
        reports.append({'month':month,'provider':provider,'currency':'USD','spend':f'{total:.2f}',
                        'monthly_budget':f'{budget:.2f}' if budget else None,
                        'budget_used_percent':str((ratio*100).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)) if ratio is not None else None,
                        'status':status,'records':len(records),
                        'service_totals':{k:f'{v:.2f}' for k,v in sorted(services.items())},
                        'environment_totals':{k:f'{v:.2f}' for k,v in sorted(environments.items())}})
    return {'scope':'Historical CSV totals; no forecasts or cloud changes','monthly_reports':reports}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'sample-costs.csv')
    parser.add_argument('--budgets',type=Path,default=ROOT/'budgets.json')
    args=parser.parse_args()
    try:
        print(json.dumps(build_report(load_costs(args.input),load_budgets(args.budgets)),indent=2))
        return 0
    except (ValueError,OSError) as exc:
        print(str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
