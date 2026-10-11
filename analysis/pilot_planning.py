"""Capacity scenarios and missing-input checks; does not score or assign donors."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import uuid


def plan_pilot(root):
    root = Path(root).resolve()
    config_path = root / 'analysis' / 'pilot_config.json'
    config = json.loads(config_path.read_text())
    required = [
        'launch_date', 'randomization_unit', 'staff_hours_available', 'setup_hours',
        'minutes_per_assigned_treatment_donor', 'max_contact_attempts', 'outreach_channel',
        'assignment_as_of_date', 'payment_data_complete_through',
        'minimum_meaningful_upgrade_rate_difference', 'currency_or_source_unit',
        'loaded_staff_hour_cost', 'fixed_pilot_cost',
        'variable_cost_per_assigned_treatment_donor', 'owner',
    ]
    confirmations = [
        'target_definition_confirmed', 'outreach_protocol_confirmed',
        'business_as_usual_defined', 'eligibility_rules_confirmed',
        'current_assignments_available', 'contact_permissions_available',
        'operational_data_available', 'sample_size_review_completed', 'stop_rules_confirmed',
    ]
    missing = [key for key in required if config.get(key) is None or config.get(key) == '']
    unconfirmed = [key for key in confirmations if config.get(key) is not True]
    scenarios = []
    # Illustrations only: donor-level randomization; setup excluded separately.
    for hours in [40, 80, 160]:
        for minutes in [20, 40, 60]:
            treatment = math.floor(max(0, hours - 8) * 60 / minutes)
            scenarios.append({'available_hours': hours, 'illustrative_setup_hours': 8,
                              'minutes_per_assigned_treatment_donor': minutes,
                              'treatment_capacity': treatment, 'control_count': treatment,
                              'total_pool': 2 * treatment})
    assert len(scenarios) == 9
    assert all(row['total_pool'] == row['treatment_capacity'] + row['control_count'] for row in scenarios)
    assert all(row['treatment_capacity'] * row['minutes_per_assigned_treatment_donor'] <=
               (row['available_hours'] - row['illustrative_setup_hours']) * 60 for row in scenarios)
    # Even completed configuration requires validation of the operational input tables.
    result = {
        'status': 'planning_only_no_assignment',
        'config_fields_complete': not missing and not unconfirmed,
        'ready_to_launch': False,
        'missing_fields': missing, 'unconfirmed_items': unconfirmed,
        'additional_gate': 'Validate actual operational tables and freeze reviewed protocol before assignment.',
        'config_sha256': hashlib.sha256(config_path.read_bytes()).hexdigest(),
        'scenarios': scenarios, 'scenario_checks_passed': 3,
        'scenarios_are_illustrative': True,
        'donors_scored': 0, 'assignments_created': 0,
    }
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    out = root / 'data' / 'pilot_planning' / run
    out.mkdir(parents=True, exist_ok=False)
    (out / 'planning_report.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'config_snapshot.json').write_text(json.dumps(config, indent=2) + '\n')
    (out / '_SUCCESS').write_text('Planning checks passed; this does not authorize or establish launch readiness.\n')
    return {'output': out, **result}
