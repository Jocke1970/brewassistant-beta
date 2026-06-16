"""Initial BrewAssistant module/capability registry."""

from __future__ import annotations

from collections.abc import Iterable

from .manifest import CapabilityManifest, CapabilityPolicy, CapabilityType, ModuleManifest, ModuleType


MODULE_MANIFESTS: dict[str, ModuleManifest] = {
    "core": ModuleManifest(
        key="core",
        name="Core",
        module_type=ModuleType.BASE,
        enabled_by_default=True,
        description="Version, module registry, diagnostics and next-action foundation.",
        capabilities=(
            CapabilityManifest("read_core_status", "Read core status", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("read_module_status", "Read module status", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("read_capability_status", "Read capability status", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
        ),
    ),
    "brewday_runtime": ModuleManifest(
        key="brewday_runtime",
        name="Brewday Runtime",
        module_type=ModuleType.BASE,
        enabled_by_default=True,
        description="Manual/Brewfather-normalized brewday process runtime.",
        optional_sources=("brewfather", "generic_recipe_runtime"),
        capabilities=(
            CapabilityManifest("read_brewday_runtime", "Read brewday runtime", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("start_manual_brewday", "Start manual brewday", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
            CapabilityManifest("pause_manual_brewday", "Pause manual brewday", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
            CapabilityManifest("finish_manual_brewday", "Finish manual brewday", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
            CapabilityManifest("handoff_to_fermentation", "Handoff to fermentation", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
        ),
        notes=("Brewday Runtime must not depend on BrewZilla.",),
    ),
    "fermentation_tracking": ModuleManifest(
        key="fermentation_tracking",
        name="Fermentation Tracking",
        module_type=ModuleType.BASE,
        enabled_by_default=True,
        description="Fermentation lifecycle and gravity/temperature tracking.",
        optional_sources=("rapt_pill", "brewfather", "generic_temperature", "fermentation_chamber"),
        capabilities=(
            CapabilityManifest("read_fermentation_status", "Read fermentation status", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("read_gravity", "Read gravity", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("read_liquid_temperature", "Read liquid temperature", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("mark_cold_crash_started", "Mark cold crash started", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
        ),
        notes=("Fermentation Tracking is base workflow; chamber control is optional.",),
    ),
    "carbonation_guidance": ModuleManifest(
        key="carbonation_guidance",
        name="Carbonation Guidance",
        module_type=ModuleType.BASE,
        enabled_by_default=True,
        description="CO2 volumes, temperature and pressure guidance.",
        optional_sources=("kegerator_temperature", "manual_temperature", "pressure_sensor"),
        capabilities=(
            CapabilityManifest("calculate_pressure", "Calculate pressure", CapabilityType.RECOMMEND, CapabilityPolicy.GUIDANCE_ONLY),
            CapabilityManifest("track_carbonation_session", "Track carbonation session", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("set_carbonation_inputs", "Set carbonation inputs", CapabilityType.CONTROL, CapabilityPolicy.DIRECT),
            CapabilityManifest("complete_carbonation", "Complete carbonation", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
        ),
    ),
    "diagnostics": ModuleManifest(
        key="diagnostics",
        name="Source Health / Diagnostics",
        module_type=ModuleType.DIAGNOSTICS,
        enabled_by_default=True,
        description="Source availability, stale data and registry cleanup summaries.",
        capabilities=(
            CapabilityManifest("read_source_health", "Read source health", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("read_registry_health", "Read registry health", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
        ),
        notes=("Large cleanup backlogs should be summarized, not listed by default.",),
    ),
    "brewzilla": ModuleManifest(
        key="brewzilla",
        name="BrewZilla",
        module_type=ModuleType.HARDWARE_ADAPTER,
        enabled_by_default=False,
        description="Hot-side adapter for BrewZilla/RAPT hardware.",
        required_sources=("rapt_cloud_link",),
        optional_sources=("shelly_power", "external_mash_temperature"),
        capabilities=(
            CapabilityManifest("read_hot_side_temperature", "Read hot-side temperature", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("read_hot_side_power", "Read hot-side power", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("set_target_temperature", "Set target temperature", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
            CapabilityManifest("control_heater", "Control heater", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
            CapabilityManifest("control_pump", "Control pump", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
            CapabilityManifest("abort_hot_side", "Abort hot-side actions", CapabilityType.SAFETY, CapabilityPolicy.DIRECT),
        ),
        notes=("BrewZilla is the first hot-side adapter, not the BrewAssistant core.",),
    ),
    "grainfather": ModuleManifest(
        key="grainfather",
        name="Grainfather",
        module_type=ModuleType.HARDWARE_ADAPTER,
        enabled_by_default=False,
        description="Future hot-side adapter for Grainfather hardware.",
        required_sources=("grainfather_integration",),
        capabilities=(
            CapabilityManifest("read_hot_side_temperature", "Read hot-side temperature", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("set_target_temperature", "Set target temperature", CapabilityType.CONTROL, CapabilityPolicy.DISABLED),
            CapabilityManifest("control_heater", "Control heater", CapabilityType.CONTROL, CapabilityPolicy.DISABLED),
            CapabilityManifest("control_pump", "Control pump", CapabilityType.CONTROL, CapabilityPolicy.DISABLED),
        ),
        notes=("Initial Grainfather support should be read-only/supervised.",),
    ),
    "kegerator": ModuleManifest(
        key="kegerator",
        name="Kegerator / Serving",
        module_type=ModuleType.OPTIONAL_MODULE,
        enabled_by_default=False,
        description="Serving fridge, cooling state and fan-auto support.",
        required_sources=("climate_or_temperature",),
        optional_sources=("power_sensor", "fan_switch", "fan_power_sensor"),
        capabilities=(
            CapabilityManifest("read_serving_temperature", "Read serving temperature", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("read_compressor_state", "Read compressor state", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("control_fan_auto", "Control fan-auto", CapabilityType.CONTROL, CapabilityPolicy.DIRECT),
            CapabilityManifest("set_serving_target", "Set serving target", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
        ),
        notes=("Compressor/cooling remains owned by the HA climate layer.",),
    ),
    "fermentation_chamber_control": ModuleManifest(
        key="fermentation_chamber_control",
        name="Fermentation Chamber Control",
        module_type=ModuleType.OPTIONAL_MODULE,
        enabled_by_default=False,
        description="Active chamber target/window management.",
        required_sources=("fermentation_chamber_climate",),
        optional_sources=("liquid_temperature", "gravity_source", "heat_mat", "fan_assist"),
        capabilities=(
            CapabilityManifest("read_chamber_temperature", "Read chamber temperature", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("calculate_chamber_target", "Calculate chamber target", CapabilityType.RECOMMEND, CapabilityPolicy.GUIDANCE_ONLY),
            CapabilityManifest("set_chamber_target", "Set chamber target", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
            CapabilityManifest("set_chamber_mode", "Set chamber mode", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
            CapabilityManifest("turn_chamber_off", "Turn chamber off", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
        ),
        notes=("Separate from Fermentation Tracking.",),
    ),
    "brewcreator_fercubator": ModuleManifest(
        key="brewcreator_fercubator",
        name="BrewCreator / Fercubator",
        module_type=ModuleType.HARDWARE_ADAPTER,
        enabled_by_default=False,
        description="Future fermentation chamber adapter for BrewCreator/Fercubator.",
        required_sources=("brewcreator_integration",),
        capabilities=(
            CapabilityManifest("read_chamber_temperature", "Read chamber temperature", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("read_chamber_target", "Read chamber target", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("set_chamber_target", "Set chamber target", CapabilityType.CONTROL, CapabilityPolicy.DISABLED),
            CapabilityManifest("set_chamber_mode", "Set chamber mode", CapabilityType.CONTROL, CapabilityPolicy.DISABLED),
        ),
        notes=("Fercubator support is a later project and should start read-only.",),
    ),
    "counterflow_chiller": ModuleManifest(
        key="counterflow_chiller",
        name="Counterflow Chiller",
        module_type=ModuleType.OPTIONAL_MODULE,
        enabled_by_default=False,
        description="Cooling and sanitation workflow support.",
        capabilities=(
            CapabilityManifest("read_cooling_status", "Read cooling status", CapabilityType.READ, CapabilityPolicy.READ_ONLY),
            CapabilityManifest("calculate_pitch_eta", "Calculate pitch ETA", CapabilityType.RECOMMEND, CapabilityPolicy.GUIDANCE_ONLY),
            CapabilityManifest("mark_cfc_ready", "Mark CFC ready", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
            CapabilityManifest("control_pump_for_cfc", "Control pump for CFC", CapabilityType.CONTROL, CapabilityPolicy.CONFIRM),
        ),
    ),
    "notifications": ModuleManifest(
        key="notifications",
        name="Notifications",
        module_type=ModuleType.OPTIONAL_MODULE,
        enabled_by_default=False,
        description="Mobile, persistent and warning notifications.",
        capabilities=(
            CapabilityManifest("send_mobile_notification", "Send mobile notification", CapabilityType.NOTIFY, CapabilityPolicy.DIRECT),
            CapabilityManifest("send_persistent_notification", "Send persistent notification", CapabilityType.NOTIFY, CapabilityPolicy.DIRECT),
            CapabilityManifest("send_warning", "Send warning", CapabilityType.NOTIFY, CapabilityPolicy.DIRECT),
        ),
        notes=("Notifications should not alert for disabled modules.",),
    ),
}


def iter_module_manifests() -> Iterable[ModuleManifest]:
    """Iterate all known module manifests."""
    return MODULE_MANIFESTS.values()


def get_module_manifest(key: str) -> ModuleManifest | None:
    """Return a module manifest by key."""
    return MODULE_MANIFESTS.get(key)


def enabled_by_default_keys() -> tuple[str, ...]:
    """Return module keys enabled by default."""
    return tuple(key for key, manifest in MODULE_MANIFESTS.items() if manifest.enabled_by_default)
