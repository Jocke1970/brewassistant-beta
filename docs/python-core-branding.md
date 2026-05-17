# BrewAssistant Python Core Branding

This guide explains how to use the BrewAssistant logo in Home Assistant dashboards.

---

## Logo source

Repository asset:

```text
pictures/BrewAssistant_color_small.png
```

Raw GitHub URL:

```text
https://raw.githubusercontent.com/Jocke1970/BrewAssistant/main/pictures/BrewAssistant_color_small.png
```

---

## Home Assistant local asset path

Home Assistant dashboards can serve static files from:

```text
/config/www/
```

Files stored there are available in Lovelace as:

```text
/local/
```

Recommended location:

```text
/config/www/brewassistant/BrewAssistant_color_small.png
```

Dashboard path:

```text
/local/brewassistant/BrewAssistant_color_small.png
```

---

## Install/update logo in Home Assistant

Run in Home Assistant Terminal / SSH:

```bash
mkdir -p /config/www/brewassistant

wget -O /config/www/brewassistant/BrewAssistant_color_small.png \
https://raw.githubusercontent.com/Jocke1970/BrewAssistant/main/pictures/BrewAssistant_color_small.png
```

---

## Simple dashboard test

```yaml
type: markdown
content: |
  <div style="text-align:center;">
    <img src="/local/brewassistant/BrewAssistant_color_small.png" width="96">
  </div>
```

---

## Notes

This is for dashboard cards only.

Home Assistant integration logos under Settings -> Devices & services use a different frontend/brand path and are not handled by this dashboard asset method.
