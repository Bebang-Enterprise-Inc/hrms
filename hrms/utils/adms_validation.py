"""
ADMS Device Validation Utilities

CRITICAL: Always validate device serial numbers AND employee Bio IDs before sending commands to ADMS.
This prevents phantom device records and enrollment of non-existent employees.

Sources of Truth:
- Device Serial Numbers: hrms/utils/device_mapping.py (46 devices)
- Employee Bio IDs: data/_FINAL/EMPLOYEE_MASTER.csv (626 employees with Bio IDs)
"""

from typing import List, Tuple, Optional, Dict
from .device_mapping import DEVICE_TO_STORE

try:
    import frappe
    _FRAPPE_AVAILABLE = True
except ImportError:
    _FRAPPE_AVAILABLE = False


class InvalidDeviceError(Exception):
    """Raised when trying to use an invalid device serial number"""
    pass


class DeviceNotFoundError(Exception):
    """Raised when device serial number is not in IT mapping"""
    pass


class EmployeeNotFoundError(Exception):
    """Raised when employee Bio ID is not in Employee_Master"""
    pass


class StoreMismatchError(Exception):
    """Raised when employee's assigned store doesn't match target device's store"""
    pass


def validate_device_serial(device_sn: str, raise_error: bool = True) -> bool:
    """
    Validate that a device serial number exists in IT mapping.

    Args:
        device_sn: Device serial number to validate
        raise_error: If True, raises DeviceNotFoundError for invalid devices

    Returns:
        True if device is valid, False otherwise

    Raises:
        DeviceNotFoundError: If device not in IT mapping and raise_error=True

    Example:
        >>> validate_device_serial('UDP3251600245')  # Valid
        True
        >>> validate_device_serial('UDP9999999999')  # Invalid - raises error
        DeviceNotFoundError: Device UDP9999999999 not in IT mapping
    """
    is_valid = device_sn in DEVICE_TO_STORE

    if not is_valid and raise_error:
        raise DeviceNotFoundError(
            f"Device {device_sn} not in IT mapping. "
            f"This will create a phantom device record in ADMS. "
            f"Valid devices are in hrms/utils/device_mapping.py (46 devices total)"
        )

    return is_valid


def validate_device_batch(device_serials: List[str]) -> Tuple[List[str], List[str]]:
    """
    Validate a batch of device serial numbers.

    Args:
        device_serials: List of device serial numbers to validate

    Returns:
        Tuple of (valid_devices, invalid_devices)

    Example:
        >>> valid, invalid = validate_device_batch(['UDP3251600245', 'UDP9999999999'])
        >>> print(valid)
        ['UDP3251600245']
        >>> print(invalid)
        ['UDP9999999999']
    """
    valid = []
    invalid = []

    for sn in device_serials:
        if validate_device_serial(sn, raise_error=False):
            valid.append(sn)
        else:
            invalid.append(sn)

    return valid, invalid


def get_valid_device_count() -> int:
    """
    Get the total number of valid devices in IT mapping.

    Returns:
        Number of valid devices (should be 46 as of Feb 2026)
    """
    return len(DEVICE_TO_STORE)


def get_device_store_name(device_sn: str) -> str:
    """
    Get the store name for a device serial number.
    Validates device exists before returning store name.

    Args:
        device_sn: Device serial number

    Returns:
        Store name for the device

    Raises:
        DeviceNotFoundError: If device not in IT mapping

    Example:
        >>> get_device_store_name('UDP3251600245')
        'BRITTANY OFFICE'
    """
    validate_device_serial(device_sn)  # Raises error if invalid
    return DEVICE_TO_STORE[device_sn]


def list_all_valid_devices() -> List[Tuple[str, str]]:
    """
    Get list of all valid device serial numbers and their store names.

    Returns:
        List of (device_serial, store_name) tuples

    Example:
        >>> devices = list_all_valid_devices()
        >>> print(f"Total valid devices: {len(devices)}")
        Total valid devices: 46
    """
    return list(DEVICE_TO_STORE.items())


# ==============================================================================
# EMPLOYEE VALIDATION (against Employee_Master)
# ==============================================================================

def _load_employee_master_from_db() -> Dict[str, dict]:
    """
    Load employee data from Frappe DB as the source of truth.

    Returns:
        Dict mapping Bio ID (attendance_device_id) to employee details.
    """
    employees_list = frappe.db.get_all(
        "Employee",
        fields=["attendance_device_id", "employee_name", "branch", "designation", "status"],
        filters={"attendance_device_id": ["!=", ""]},
    )
    result = {}
    for emp in employees_list:
        bio_id = (emp.attendance_device_id or "").strip()
        if bio_id:
            result[bio_id] = {
                "name": emp.employee_name or "",
                "store": emp.branch or "",
                "designation": emp.designation or "",
                "status": emp.status or "",
            }
    return result


def _get_employee_cache() -> Dict[str, dict]:
    """
    Return employee data from Frappe cache (5-minute TTL), re-querying DB on miss.
    """
    cache_key = f"employee_master_cache_{frappe.local.site}"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached
    result = _load_employee_master_from_db()
    frappe.cache().set_value(cache_key, result, expires_in_sec=300)
    return result


def get_employee_master() -> Dict[str, dict]:
    """
    Get employee data, using Frappe cache with 5-minute TTL.

    Returns:
        Dict mapping Bio ID to employee details.
    """
    return _get_employee_cache()


def validate_employee_bio_id(bio_id: str, raise_error: bool = True) -> bool:
    """
    Validate that an employee Bio ID exists in Employee_Master.

    Args:
        bio_id: Employee Bio ID to validate
        raise_error: If True, raises EmployeeNotFoundError for invalid Bio IDs

    Returns:
        True if Bio ID is valid, False otherwise

    Raises:
        EmployeeNotFoundError: If Bio ID not in Employee_Master and raise_error=True

    Example:
        >>> validate_employee_bio_id('9000123')  # Valid
        True
        >>> validate_employee_bio_id('9999999')  # Invalid - raises error
        EmployeeNotFoundError: Bio ID 9999999 not in Employee_Master
    """
    employees = get_employee_master()
    is_valid = bio_id in employees

    if not is_valid and raise_error:
        raise EmployeeNotFoundError(
            f"Bio ID {bio_id} not in Employee_Master. "
            f"Cannot enroll non-existent employee. "
            f"Total employees in master: {len(employees)}"
        )

    return is_valid


def validate_employee_batch(bio_ids: List[str]) -> Tuple[List[str], List[str]]:
    """
    Validate a batch of employee Bio IDs.

    Args:
        bio_ids: List of Bio IDs to validate

    Returns:
        Tuple of (valid_bio_ids, invalid_bio_ids)

    Example:
        >>> valid, invalid = validate_employee_batch(['9000123', '9999999'])
        >>> print(valid)
        ['9000123']
        >>> print(invalid)
        ['9999999']
    """
    valid = []
    invalid = []

    for bio_id in bio_ids:
        if validate_employee_bio_id(bio_id, raise_error=False):
            valid.append(bio_id)
        else:
            invalid.append(bio_id)

    return valid, invalid


def get_employee_details(bio_id: str) -> dict:
    """
    Get employee details from Employee_Master.
    Validates Bio ID exists before returning details.

    Args:
        bio_id: Employee Bio ID

    Returns:
        Dict with employee details {name, store, designation, status}

    Raises:
        EmployeeNotFoundError: If Bio ID not in Employee_Master

    Example:
        >>> details = get_employee_details('9000123')
        >>> print(details['name'])
        'SANTOS, JUAN D.'
    """
    validate_employee_bio_id(bio_id)  # Raises error if invalid
    employees = get_employee_master()
    return employees[bio_id]


def get_employee_count() -> int:
    """
    Get the total number of employees with Bio IDs in Employee_Master.

    Returns:
        Number of employees (should be 626 as of Feb 2026)
    """
    employees = get_employee_master()
    return len(employees)


def validate_store_assignment(bio_id: str, device_sn: str, raise_error: bool = True) -> bool:
    """
    Validate that employee's assigned store matches the device's store.

    Args:
        bio_id: Employee Bio ID
        device_sn: Device serial number
        raise_error: If True, raises StoreMismatchError for mismatches

    Returns:
        True if stores match, False otherwise

    Raises:
        EmployeeNotFoundError: If Bio ID not in Employee_Master
        DeviceNotFoundError: If device not in IT mapping
        StoreMismatchError: If stores don't match and raise_error=True

    Example:
        >>> # Employee works at Brittany, device is at Brittany
        >>> validate_store_assignment('9000123', 'UDP3251600245')  # OK
        True
        >>> # Employee works at SM Clark, device is at Brittany
        >>> validate_store_assignment('9000456', 'UDP3251600245')  # ERROR
        StoreMismatchError: Employee at SM CLARK but device at BRITTANY OFFICE
    """
    # Get employee store
    employee = get_employee_details(bio_id)
    employee_store = employee['store'].strip().upper()

    # Get device store
    device_store = get_device_store_name(device_sn).strip().upper()

    # Normalize store names for comparison
    store_mappings = {
        'AYALA FAIRVIEW TERRACES': 'AYALA FAIRVIEW',
        'SM CLARK': 'SM CITY CLARK',
        'ROBINSONS ANTIPOLO': 'ROBINSON ANTIPOLO',
        'ROBINSONS GENERAL TRIAS': 'ROBINSON GENTRI',
        'GRAND CENTRAL': 'SM GRAND CENTRAL',
        'SM EAST ORTIGAS': 'SMEO',
        'VENICE GRAND CANAL': 'VENICE GRAND',
        'ROBINSONS IMUS': 'ROB IMUS',
        'ROBINSON GALLERIA SOUTH': 'ROBINSON GALLERIA S',
        'STA LUCIA GRAND MALL': 'STA.LUCIA',
        'D VERDE CALAMBA': "D'VERDE",
        'NAIA T3': 'NAIA',
        'SHAW COMMISSARY': 'SHAW',
        'BGC': 'BGC CAPITAL HOUSE',
        'BRITTANY': 'BRITANY OFFICE',
    }

    normalized_emp_store = store_mappings.get(employee_store, employee_store)
    normalized_dev_store = store_mappings.get(device_store, device_store)

    matches = normalized_emp_store == normalized_dev_store

    if not matches and raise_error:
        raise StoreMismatchError(
            f"Employee {bio_id} ({employee['name']}) works at {employee_store} "
            f"but device {device_sn} is at {device_store}. "
            f"Employee should be enrolled at their assigned store's device."
        )

    return matches


# Validation decorator for ADMS command functions
def require_valid_device(func):
    """
    Decorator to validate device serial number before executing ADMS commands.

    Usage:
        @require_valid_device
        def enroll_user(device_sn: str, bio_id: str, name: str):
            # Function will only execute if device_sn is valid
            pass
    """
    def wrapper(device_sn: str, *args, **kwargs):
        validate_device_serial(device_sn)  # Raises error if invalid
        return func(device_sn, *args, **kwargs)
    return wrapper


# Example usage for ADMS enrollment
@require_valid_device
def send_enrollment_command(device_sn: str, bio_id: str, employee_name: str) -> str:
    """
    Example function showing safe enrollment with validation.

    This is a template - actual implementation should use AWS SSM
    to send commands to ADMS.

    Args:
        device_sn: Device serial number (validated before execution)
        bio_id: Employee Bio ID
        employee_name: Employee full name

    Returns:
        SQL command text to insert into adms_device_cmd

    Raises:
        DeviceNotFoundError: If device_sn is not in IT mapping
    """
    # Device is already validated by decorator
    command_text = f"DATA UPDATE USERINFO PIN={bio_id}\tName={employee_name}\tPri=0"

    sql = f"""
    INSERT INTO adms_device_cmd (sn, command_text, status, attempts, created_at, updated_at)
    VALUES ('{device_sn}', '{command_text}', 'PENDING', 0, NOW(), NOW());
    """

    return sql


# CRITICAL SAFEGUARD: Pre-flight check function
def preflight_check_enrollment(enrollments: List[Tuple[str, str, str]],
                               check_store_match: bool = True) -> dict:
    """
    Pre-flight validation for batch enrollment.
    Call this BEFORE sending any commands to ADMS.

    Validates:
    1. Device serial numbers exist in IT mapping (46 devices)
    2. Employee Bio IDs exist in Employee_Master (626 employees)
    3. Employee's assigned store matches device's store (optional)

    Args:
        enrollments: List of (device_sn, bio_id, employee_name) tuples
        check_store_match: If True, validates employee store matches device store

    Returns:
        Dict with validation results and errors

    Example:
        >>> enrollments = [
        ...     ('UDP3251600245', '9000123', 'SMITH, JOHN'),  # Valid
        ...     ('UDP9999999999', '9000456', 'DOE, JANE'),    # Invalid device
        ...     ('UDP3251600245', '9999999', 'FAKE, USER'),   # Invalid employee
        ... ]
        >>> result = preflight_check_enrollment(enrollments)
        >>> if not result['can_proceed']:
        ...     print(f"ERROR: {result['error_message']}")
        ...     raise Exception("Cannot proceed with validation errors")
    """
    all_devices = [enrollment[0] for enrollment in enrollments]
    all_bio_ids = [enrollment[1] for enrollment in enrollments]

    # Validate devices
    valid_devices, invalid_devices = validate_device_batch(all_devices)

    # Validate employees
    valid_employees, invalid_employees = validate_employee_batch(all_bio_ids)

    # Validate store assignments (if enabled)
    store_mismatches = []
    if check_store_match:
        for device_sn, bio_id, _ in enrollments:
            # Only check if both device and employee are valid
            if device_sn in valid_devices and bio_id in valid_employees:
                if not validate_store_assignment(bio_id, device_sn, raise_error=False):
                    employee = get_employee_details(bio_id)
                    device_store = get_device_store_name(device_sn)
                    store_mismatches.append({
                        'bio_id': bio_id,
                        'name': employee['name'],
                        'employee_store': employee['store'],
                        'device': device_sn,
                        'device_store': device_store
                    })

    # Build error messages
    errors = []
    if invalid_devices:
        errors.append(
            f"Invalid devices ({len(invalid_devices)}): {', '.join(invalid_devices[:5])}"
            + (f" and {len(invalid_devices)-5} more" if len(invalid_devices) > 5 else "")
        )
    if invalid_employees:
        errors.append(
            f"Invalid Bio IDs ({len(invalid_employees)}): {', '.join(invalid_employees[:5])}"
            + (f" and {len(invalid_employees)-5} more" if len(invalid_employees) > 5 else "")
        )
    if store_mismatches:
        errors.append(
            f"Store mismatches ({len(store_mismatches)}): "
            f"Employees assigned to different stores than target devices"
        )

    can_proceed = len(invalid_devices) == 0 and len(invalid_employees) == 0 and len(store_mismatches) == 0

    return {
        'total': len(enrollments),
        'valid_devices': len(valid_devices),
        'invalid_devices': invalid_devices,
        'valid_employees': len(valid_employees),
        'invalid_employees': invalid_employees,
        'store_mismatches': store_mismatches,
        'can_proceed': can_proceed,
        'error_message': ' | '.join(errors) if errors else None,
        'details': {
            'total_employees_in_master': get_employee_count(),
            'total_valid_devices': get_valid_device_count()
        }
    }
