"""Unified MCP registry and JSON-RPC 2.0 gateway for the three KrishiNexus servers.

* ``GATEWAY`` serves all 13 tools behind one JSON-RPC endpoint (``POST /mcp``, ``POST /mcp/call``).
* ``SERVER_DISPATCHERS`` expose each server on its own Streamable HTTP endpoint
  (``POST /mcp/servers/<name>``), mirroring the standalone stdio processes.
* ``simulate_anomaly`` lets judges inject a cold-chamber power cut or a haor flash
  flood during the live demo and returns the immediate tool-level impact.
"""

from __future__ import annotations

from config import settings
from mcp_servers import agri_weather_sar_mcp, bd_geo, coldchain_iot_mcp, dam_market_mcp
from mcp_servers.anomaly_state import ANOMALIES, ActiveAnomaly
from mcp_servers.base import JsonRpcDispatcher, McpServer, ToolExecutionError, standalone_dispatcher
from schemas.mcp_models import (
    ActiveAnomalyView,
    CalculateHaorFlashFloodRiskInput,
    FlashFloodAnomalyRequest,
    GetChamberTelemetryInput,
    McpServerDescriptor,
    McpToolDescriptor,
    McpToolsListing,
    PowerCutAnomalyRequest,
    SimulateAnomalyResponse,
)

SERVERS: tuple[McpServer, ...] = (
    dam_market_mcp.server,
    agri_weather_sar_mcp.server,
    coldchain_iot_mcp.server,
)
SERVERS_BY_NAME: dict[str, McpServer] = {server.name: server for server in SERVERS}

GATEWAY = JsonRpcDispatcher(
    SERVERS,
    name="krishinexus-mcp-gateway",
    title="KrishiNexus OS MCP Gateway",
    version=settings.app_version,
    instructions=(
        "KrishiNexus OS exposes 13 tools for Bangladeshi smallholder agriculture: market spreads and "
        "syndicate markup detection (dam-market-mcp), weather, haor flash-flood risk and early harvest "
        "(agri-weather-sar-mcp), and BCSA cold-storage quota, telemetry, shelf life and warehouse "
        "receipts (coldchain-iot-mcp). Prices are Tk/kg; times are BDT (UTC+06:00)."
    ),
)
SERVER_DISPATCHERS: dict[str, JsonRpcDispatcher] = {
    server.name: standalone_dispatcher(server) for server in SERVERS
}


def server_descriptors(base_url: str) -> list[McpServerDescriptor]:
    return [
        McpServerDescriptor(
            name=server.name,
            title=server.title,
            version=server.version,
            description=server.description,
            protocol_version=settings.mcp_protocol_version,
            transports=list(server.transports),
            endpoint=f"{base_url}/mcp/servers/{server.name}",
            stdio_command=f"python -m {server.module}",
            tool_count=len(server.tools),
            tools=[spec.name for spec in server.tools],
        )
        for server in SERVERS
    ]


def tools_listing(server_name: str | None = None) -> McpToolsListing:
    selected = [SERVERS_BY_NAME[server_name]] if server_name else list(SERVERS)
    tools = [
        McpToolDescriptor(
            server=server.name,
            name=spec.name,
            title=spec.title,
            description=spec.description,
            inputSchema=spec.input_model.model_json_schema(),
            outputSchema=spec.output_model.model_json_schema(mode="serialization"),
            annotations=spec.annotations(),
        )
        for server in selected
        for spec in server.tools
    ]
    return McpToolsListing(count=len(tools), servers=[s.name for s in selected], tools=tools)


def anomaly_view(anomaly: ActiveAnomaly) -> ActiveAnomalyView:
    return ActiveAnomalyView(
        anomaly_id=anomaly.anomaly_id,
        anomaly_type=anomaly.anomaly_type,
        target=anomaly.target,
        params=dict(anomaly.params),
        activated_at=anomaly.activated_at,
        expires_at=anomaly.expires_at,
    )


async def simulate_anomaly(request: PowerCutAnomalyRequest | FlashFloodAnomalyRequest) -> SimulateAnomalyResponse:
    """Inject a live-demo anomaly and return what the affected MCP tool now reports."""
    match request:
        case PowerCutAnomalyRequest():
            facility = coldchain_iot_mcp.get_facility(request.facility_id)
            chamber = coldchain_iot_mcp.validate_chamber(facility, request.chamber_id) if request.chamber_id else None
            anomaly = ANOMALIES.inject(
                "cold_chamber_power_cut",
                f"{facility.facility_id}/{chamber or 'ALL-CHAMBERS'}",
                {
                    "facility_id": facility.facility_id,
                    "chamber_id": chamber,
                    "generator_failed": request.generator_failed,
                    "elapsed_minutes": request.elapsed_minutes,
                },
                request.duration_minutes,
            )
            preview = await coldchain_iot_mcp.get_chamber_telemetry(
                GetChamberTelemetryInput(facility_id=facility.facility_id, chamber_id=chamber or "CH-01")
            )
            message = (
                f"Power cut injected at {facility.name} ({anomaly.target}); "
                + ("generator failed, compressors stopped." if request.generator_failed else "diesel backup running.")
                + f" Chamber now {preview.temperature_c:.1f} C with {preview.rot_risk_pct:.1f}% rot risk."
            )
            return SimulateAnomalyResponse(
                anomaly=anomaly_view(anomaly),
                message=message,
                impact_tool="get_chamber_telemetry",
                impact_preview=preview.model_dump(mode="json"),
            )
        case FlashFloodAnomalyRequest():
            upazila = bd_geo.resolve_upazila(request.upazila)
            if upazila.name not in agri_weather_sar_mcp.HAOR_UPAZILAS:
                raise ToolExecutionError(
                    f"'{upazila.name}' is not a haor upazila. Choose one of: "
                    f"{', '.join(agri_weather_sar_mcp.HAOR_UPAZILAS)}."
                )
            anomaly = ANOMALIES.inject(
                "haor_flash_flood",
                f"{upazila.district}/{upazila.name}",
                {
                    "upazila": upazila.name,
                    "district": upazila.district,
                    "upstream_rainfall_72h_mm": request.upstream_rainfall_72h_mm,
                    "sar_water_backscatter_db": request.sar_water_backscatter_db,
                    "scenario_month": request.scenario_month,
                },
                request.duration_minutes,
            )
            flood = await agri_weather_sar_mcp.calculate_haor_flash_flood_risk(
                CalculateHaorFlashFloodRiskInput(
                    upazila=upazila.name, sar_water_backscatter_db=request.sar_water_backscatter_db
                )
            )
            message = (
                f"Flash flood injected over {upazila.district}: {request.upstream_rainfall_72h_mm:.0f} mm upstream "
                f"rain in 72 h. {upazila.name} breach probability {flood.embankment_breach_probability_pct:.1f}% "
                f"({flood.alert_level.value}); harvest within {flood.recommended_harvest_within_hours:.0f} h."
            )
            return SimulateAnomalyResponse(
                anomaly=anomaly_view(anomaly),
                message=message,
                impact_tool="calculate_haor_flash_flood_risk",
                impact_preview=flood.model_dump(mode="json"),
            )


async def shutdown() -> None:
    await agri_weather_sar_mcp.aclose_http_client()
