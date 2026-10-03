# GF30 cloud-link recovery field note — 2026-10-01

Status: **field-verified recovery / onboarding workaround**

Hardware: Grainfather GF30 Conical Fermenter with Wi-Fi controller  
Result: GF30 joined Wi-Fi, was linked to the Grainfather account, produced Grainfather cloud telemetry, and became visible to Home Assistant.

> This note documents what was observed and what solved the specific installation. It is not an official Grainfather procedure, and Grainfather/Particle behavior may change.

## Problem

The Grainfather Android app could discover the GF30 setup network but repeatedly failed to complete setup, asking for the Conical Fermenter Pro to be restarted and setup retried.

Changing the 2.4 GHz SSID to a simpler temporary name did not resolve the failure.

Direct scanning from the controller later proved that the intended 2.4 GHz WLAN was visible with strong signal and compatible WPA2/AES security. SSID formatting was therefore ruled out as the root cause.

## What we discovered

The recovery turned out to contain two separate problems:

```text
1. Provision controller Wi-Fi
2. Link the already networked controller to the Grainfather account
```

Completing only the first step was not sufficient.

## SoftAP inspection

The GF30 was put into **Add New Network / listening mode**.

A Linux computer connected to the temporary Grainfather controller access point. The controller appeared as the gateway on the temporary setup network.

The controller exposed a Particle-style SoftAP setup service. Inspection confirmed:

- a small HTTP setup surface;
- an access-point scan endpoint;
- a controller public key;
- Particle SoftAP protocol version 2 on TCP 5609;
- a controller/device identifier returned by the SoftAP protocol.

The access-point scan confirmed that the intended garage 2.4 GHz network was visible directly from the GF30.

The SoftAP device information also showed that network provisioning and account ownership/linking were separate states.

## Manual Wi-Fi provisioning

The controller's own SoftAP provisioning flow was used instead of the failing Grainfather app wizard.

The flow used:

1. the controller-provided Wi-Fi scan;
2. the controller-provided public key;
3. locally encrypted Wi-Fi credentials;
4. the controller's configure/connect operations.

No Wi-Fi password or encrypted payload is retained in this repository.

The controller accepted the configuration and joined the normal LAN successfully.

Observed end state at this point:

```text
GF30 Wi-Fi connected          ✅
temporary setup AP gone       ✅
normal LAN address assigned   ✅
Grainfather account link      ❌
```

This was the key finding: **successful Wi-Fi provisioning did not automatically complete Grainfather account/controller linking**.

## Particle claim-code investigation

The Particle device-setup SDK was inspected because the SoftAP protocol exposed a claimed-state field.

Particle's setup protocol includes a separate claim-code concept. That confirmed that Wi-Fi provisioning and cloud ownership are logically separate.

However, the GF30 was **not** manually claimed into a personal Particle account and no guessed claim code was used. That route was abandoned because Grainfather should remain the owning product/account system.

## Grainfather Android application inspection

The installed Grainfather Android application was pulled from an Android phone through ADB. The app is installed as a base APK plus split APKs, so all installed parts were collected for inspection.

Package:

```text
za.co.digitlab.GFConnect
```

Inspection of the application code exposed the missing Grainfather-side controller-link flow.

The relevant conceptual sequence was:

```text
Grainfather account login
        |
        v
list fermentation equipment
        |
        v
identify GF30 equipment record
        |
        v
link controller to that equipment record
        |
        v
reload/verify equipment state
```

The app links the controller using the controller identifier as the GF30's ESP/controller identity while leaving the legacy Particle device identifier empty.

## Account link result

Before linking, the existing Grainfather GF30 equipment record showed conceptually:

```text
GF30 equipment exists
controller-linked = false
ESP/controller id = empty
Particle device id = empty
```

After performing the same controller-link operation used by the Grainfather app:

```text
GF30 equipment exists
controller-linked = true
ESP/controller id = assigned
Particle device id = empty
```

The server returned success and a second read confirmed that the linked state persisted.

## Verified final state

After Wi-Fi provisioning plus Grainfather account linking:

```text
GF30 Wi-Fi                         ✅
normal LAN connectivity            ✅
Grainfather equipment record       ✅
controller linked                  ✅
Grainfather cloud telemetry        ✅
Home Assistant GF30 temperature    ✅
```

Home Assistant later reported a fermentation-device entity with:

```yaml
grainfather_entity_type: fermentation_device
is_controller_linked: true
```

and a valid GF30 internal temperature.

## Additional telemetry finding

The current upstream Home Assistant Grainfather integration exposes temperature and gravity for fermentation devices.

Direct inspection of the Grainfather GF30 history data showed that the same cloud data also contains:

```text
temperature
target_temperature
```

Therefore target temperature is confirmed to exist in the Grainfather cloud data even though the current upstream integration does not expose it as its own Home Assistant entity.

This is useful for the next BrewAssistant GF30 telemetry phase.

## Security notes

The repository must not contain:

- Grainfather account passwords;
- Grainfather bearer/API tokens;
- Particle access tokens;
- Wi-Fi passwords;
- encrypted Wi-Fi credential payloads copied from a live setup.

If any credential is exposed during troubleshooting, rotate it.

## Practical recovery sequence

The sequence that solved this installation was:

```text
GF30 app setup failed
  -> enter controller SoftAP/listening mode
  -> verify controller can see intended 2.4 GHz WLAN
  -> identify Particle-style SoftAP/device state
  -> provision Wi-Fi using the controller's own setup flow
  -> verify GF30 joins LAN
  -> observe that Grainfather account is still unlinked
  -> inspect Grainfather Android client
  -> identify Grainfather controller-link flow
  -> link the existing GF30 equipment record to the controller identity
  -> verify controller-linked state
  -> verify Grainfather cloud telemetry
  -> verify Home Assistant telemetry
```

## What this does not validate

This recovery proves connectivity and account association only.

It does not by itself validate:

- BrewAssistant target writes;
- unattended Grainfather control;
- heating/cooling command semantics;
- cooling-pump ownership;
- cloud outage behavior;
- future firmware/app/API compatibility.

Those remain separate live-hardware validation tasks.
