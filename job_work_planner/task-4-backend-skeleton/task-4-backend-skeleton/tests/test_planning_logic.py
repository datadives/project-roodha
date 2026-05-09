import pytest

# We isolate the exact logic from your planning_service.py to test it instantly
def calculate_machine_load_hours(quantity: int, cycle_time_minutes: float) -> float:
    # This is the V1.5 stabilization fallback logic
    safe_cycle_time = cycle_time_minutes if cycle_time_minutes and cycle_time_minutes > 0 else 1.0
    required_minutes = quantity * safe_cycle_time
    return required_minutes / 60.0

def test_division_by_zero_guard():
    """Test that an operation with 0 cycle time doesn't crash, but falls back to 1 minute."""
    load = calculate_machine_load_hours(quantity=600, cycle_time_minutes=0)
    # 600 parts * 1 min fallback = 600 mins = 10.0 hours
    assert load == 10.0

def test_null_cycle_time_guard():
    """Test that an operation with None/Null cycle time falls back to 1 minute."""
    load = calculate_machine_load_hours(quantity=300, cycle_time_minutes=None)
    # 300 parts * 1 min fallback = 300 mins = 5.0 hours
    assert load == 5.0

def test_normal_calculation():
    """Test that a normal operation calculates perfectly."""
    load = calculate_machine_load_hours(quantity=100, cycle_time_minutes=6.0)
    # 100 parts * 6 mins = 600 mins = 10.0 hours
    assert load == 10.0