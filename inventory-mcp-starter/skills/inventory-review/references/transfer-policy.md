# Demo transfer policy and reviewer checklist

This reference explains the fictional example. Call `get_policy` for the structured limits used by the server. The scenario and deterministic checks are reused from the earlier inventory-agent starter.

## Data and calculation scope

- Item: SKU-DEMO-100, measured in individual units (EA).
- Destination: DXB-WH, Dubai. On hand 100, reserved 20, available 80; additional daily demand 40.
- Source: AUH-WH, Abu Dhabi. On hand 660, reserved 60, available 600; additional daily demand 30.
- Travel time: one day. Transport cost: AED 300 (30,000 minor units).
- Standard supplier lead: ten days.
- Target destination cover at arrival: seven days; maximum ten days.
- Minimum source cover at arrival: seven days. Pack size ten; maximum 1,000 units.
- Transport budget: AED 500. Every proposal requires procurement review.

For 240 units, destination stock just before arrival is 80 - 40 = 40. After arrival, 40 + 240 = 280, or seven days of cover. Source stock projected at arrival is 600 - 240 - 30 = 330, or eleven days of cover. Both checks pass.

This is a constant-demand teaching model. It refuses invalid forecasts, unsupported units and aggregate inbound supply. It is not a time-phased stock projection, and the fixed fixture does not represent fresh operational stock. Its `as_of` timestamp records when the fixture was read.

## Review output

Show the item, source/destination, quantity and unit, travel time, transport cost/currency, before/after stock and coverage, evidence versions and timestamps, assumptions, alternative, proposal ID/hash, expiry and review status. Proposals expire after one hour. A changed proposal, inventory snapshot or policy requires a new review before simulation.

The human reviewer decides to approve or reject the exact proposal hash. The demo CLI records a label and comment, then optionally writes a local simulation receipt. It does not change the fixture, move stock or create an ERP document. Multiple proposals do not reserve stock; a production executor must reconcile concurrent requests against live stock atomically.
