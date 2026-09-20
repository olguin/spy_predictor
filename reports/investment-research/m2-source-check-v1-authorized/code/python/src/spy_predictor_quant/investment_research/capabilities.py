"""Credential-free inventory; presence is not a successful provider request."""
import os


def inventory(mandate: dict) -> dict:
    groups = {"alpaca": ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY"), "fred": ("FRED_API_KEY",),
              "sec": ("SEC_USER_AGENT",), "massive": ("MASSIVE_API_KEY",)}
    return {"schema_version": "investment-research-capabilities-v1",
            "configured_source_ids": [s["source_id"] for s in mandate["sources"]],
            "discovery": "REGISTERED_INDEX_ONLY", "general_web_search": False,
            "network_enabled": mandate["network"]["enabled"],
            "credentials": {name: {"environment_present": all(bool(os.environ.get(k)) for k in keys),
                                   "access_verified": False,
                                   "research_broker_adapter": "SEC_CURRENT_DOCUMENTS_AND_FACTS" if name == "sec" else "NOT_IMPLEMENTED"} for name, keys in groups.items()},
            "note": "No credential values are recorded. Environment presence does not prove source coverage or access."}
