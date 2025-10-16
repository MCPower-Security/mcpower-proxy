import copy
from typing import TypeVar, Dict, Any

T = TypeVar('T')


def safe_copy(obj: T, update_dict: Dict[str, Any] = None) -> T:
    """
    Safely copy an object (Pydantic model or regular object) with optional updates.

    Args:
        obj: The object to copy (can be Pydantic model or regular object)
        update_dict: Optional dictionary of field updates to apply

    Returns:
        A copy of the object with updates applied
    """
    if update_dict is None:
        update_dict = {}

    # Try Pydantic model_copy first (v2)
    if hasattr(obj, 'model_copy'):
        return obj.model_copy(update=update_dict)

    # Try generic copy method (v1 or custom objects)
    elif hasattr(obj, 'copy'):
        return obj.copy(update=update_dict)

    # Fallback to manual copying for regular objects
    else:
        # Use deepcopy to match original behavior and ensure complete isolation
        new_obj = copy.deepcopy(obj)
        # Apply updates
        for key, value in update_dict.items():
            setattr(new_obj, key, value)
        return new_obj
