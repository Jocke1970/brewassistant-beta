const CARD_TYPE = 'brewassistant-temperature-gauge';
const CARD_VERSION = '0.1.1-draft';

class BrewAssistantTemperatureGauge extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = null;
    this._hass = null;
  }

  setConfig(config) {
    if (!config) throw new Error('Missing card configuration');

    this._config = {
      min: 20,
      max: 80,
      precision_tolerance: 0.3,
      quality_tolerance: 1.0,
      background_tolerance: 1.5,
      mash_entity: 'sensor.brewassistant_brewzilla_mash_temperature',
      wort_entity: 'sensor.brewassistant_brewzilla_wort_temperature',
      mash_source_entity: 'sensor.brewassistant_brewzilla_mash_temperature_source',
      delta_entity: 'sensor.brewassistant_brewzilla_temperature_delta_mash_wort',
      orchestration_entity: 'sensor.brewassistant_brewzilla_orchestration_mode',
      requested_target_entity: 'sensor.brewassistant_brewzilla_requested_target',
      runtime_target_entity: 'sensor.brewassistant_brewzilla_runtime_target_temperature',
      ba_target_entity: 'sensor.brewassistant_brewzilla_target_temperature',
      device_target_entity: 'sensor.brewassistant_brewzilla_device_target_temperature',
      ...config,
    };

    if (Number(this._config.max) <= Number(this._config.min)) {
      throw new Error('max must be greater than min');
    }

    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig() {
    return { type: `custom:${CARD_TYPE}` };
  }

  _state(id) {
    return id ? this._hass?.states?.[id] : undefined;
  }

  _num(value) {
    if (value === undefined || value === null) return null;
    const raw = String(value).trim().replace(',', '.');
    if (!raw || ['unknown', 'unavailable', 'none', 'null'].includes(raw.toLowerCase())) return null;
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  }

  _stateNum(id) {
    return this._num(this._state(id)?.state);
  }

  _bool(value) {
    if (value === true) return true;
    const raw = String(value ?? '').toLowerCase();
    return ['true', 'on', 'yes', '1'].includes(raw);
  }

  _lang() {
    const lang = String(this._hass?.language || 'sv').toLowerCase();
    return lang.startsWith('sv') ? 'sv' : 'en';
  }

  _t(sv, en) {
    return this._lang() === 'sv' ? sv : en;
  }

  _fmt(value, decimals = 1) {
    if (!Number.isFinite(value)) return '—';
    return value.toFixed(decimals);
  }

  _target() {
    const c = this._config;
    const orch = this._state(c.orchestration_entity);
    const attrs = orch?.attributes || {};
    const heatstrike = this._bool(attrs.heat_strike_latch_active);
    const strike = this._num(attrs.heat_strike_target);

    if (heatstrike && strike !== null) return strike;

    for (const entityId of [
      c.requested_target_entity,
      c.runtime_target_entity,
      c.ba_target_entity,
      c.device_target_entity,
    ]) {
      const value = this._stateNum(entityId);
      if (value !== null && value > 0) return value;
    }
    return null;
  }

  _phase() {
    const c = this._config;
    const orch = this._state(c.orchestration_entity);
    const attrs = orch?.attributes || {};
    const mode = String(orch?.state ?? '').toLowerCase();
    const heatstrike = this._bool(attrs.heat_strike_latch_active);
    const degraded = this._bool(attrs.rcl_degraded) || this._bool(attrs.heat_strike_rcl_degraded);
    const source = String(this._state(c.mash_source_entity)?.state ?? '');
    const physicalPhase = String(attrs.advice_physical_phase ?? '');

    if (degraded) {
      return {
        icon: 'mdi:connection',
        label: this._t('RCL degraderad', 'RCL degraded'),
        title: this._t('RCL degraderad · styrning blockerad', 'RCL degraded · control blocked'),
      };
    }

    if (mode === 'blocked') {
      return {
        icon: 'mdi:lock-outline',
        label: this._t('blockerad', 'blocked'),
        title: this._t('Mäsk · BrewZilla Internal', 'Mash · BrewZilla Internal'),
      };
    }

    if (heatstrike) {
      return {
        icon: 'mdi:kettle-steam-outline',
        label: 'heatstrike',
        title: physicalPhase === 'pre_mash_in_paused_wait'
          ? this._t('Heatstrike · väntar på inmäskning', 'Heat strike · waiting for mash-in')
          : this._t('Heatstrike · strikevatten', 'Heat strike · strike water'),
      };
    }

    if (source === 'RAPT BLE Thermometer') {
      return {
        icon: 'mdi:thermometer-bluetooth',
        label: this._t('BLE mäsk', 'BLE mash'),
        title: this._t('Mäsk/BLE · RAPT BLE', 'Mash/BLE · RAPT BLE'),
      };
    }

    return {
      icon: 'mdi:thermometer-probe',
      label: this._t('mäsk', 'mash'),
      title: source && !['unknown', 'unavailable', 'none'].includes(source.toLowerCase())
        ? `${this._t('Mäsk', 'Mash')} · ${source}`
        : this._t('BrewZilla mäsk/vört', 'BrewZilla mash/wort'),
    };
  }

  _clamp(value) {
    const min = Number(this._config.min);
    const max = Number(this._config.max);
    if (!Number.isFinite(value)) return null;
    return Math.max(min, Math.min(max, value));
  }

  _angle(value) {
    const min = Number(this._config.min);
    const max = Number(this._config.max);
    const clamped = this._clamp(value);
    if (clamped === null) return null;
    return 200 + ((clamped - min) / (max - min)) * 140;
  }

  _point(angle, radius, cx = 130, cy = 112) {
    const rad = angle * Math.PI / 180;
    return {
      x: cx + radius * Math.cos(rad),
      y: cy + radius * Math.sin(rad),
    };
  }

  _arcPath(fromValue, toValue, radius = 92, steps = 28) {
    if (!Number.isFinite(fromValue) || !Number.isFinite(toValue)) return '';
    const a0 = this._angle(Math.min(fromValue, toValue));
    const a1 = this._angle(Math.max(fromValue, toValue));
    if (a0 === null || a1 === null) return '';

    const points = [];
    for (let i = 0; i <= steps; i += 1) {
      const angle = a0 + (a1 - a0) * (i / steps);
      const point = this._point(angle, radius);
      points.push(`${i === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`);
    }
    return points.join(' ');
  }

  _needle(value, radius = 87, startRadius = 16) {
    const angle = this._angle(value);
    if (angle === null) return null;
    return {
      start: this._point(angle, startRadius),
      end: this._point(angle, radius),
    };
  }

  _marker(value, innerRadius = 95, outerRadius = 104) {
    const angle = this._angle(value);
    if (angle === null) return null;
    return {
      inner: this._point(angle, innerRadius),
      outer: this._point(angle, outerRadius),
    };
  }

  _render() {
    if (!this.shadowRoot || !this._config || !this._hass) return;

    const c = this._config;
    const mash = this._stateNum(c.mash_entity);
    const wort = this._stateNum(c.wort_entity);
    const target = this._target();
    const delta = mash !== null && wort !== null ? wort - mash : null;
    const phase = this._phase();

    const mashNeedle = this._needle(mash, 87, 16);
    const wortNeedle = this._needle(wort, 69, 20);
    const targetMarker = this._marker(target);
    const quality = Number(c.quality_tolerance);
    const precision = Number(c.precision_tolerance);
    const basePath = this._arcPath(Number(c.min), Number(c.max));
    const qualityPath = target !== null ? this._arcPath(target - quality, target + quality) : '';
    const precisionPath = target !== null ? this._arcPath(target - precision, target + precision) : '';

    const line = (needle, cls) => needle
      ? `<line class="needle ${cls}" x1="${needle.start.x}" y1="${needle.start.y}" x2="${needle.end.x}" y2="${needle.end.y}" />`
      : '';

    const targetLine = targetMarker
      ? `<line class="target-marker" x1="${targetMarker.inner.x}" y1="${targetMarker.inner.y}" x2="${targetMarker.outer.x}" y2="${targetMarker.outer.y}" />`
      : '';

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card {
          position: relative;
          overflow: hidden;
          border-radius: 18px;
          border: 1px solid var(--divider-color);
          min-height: 190px;
          background: var(--ha-card-background, var(--card-background-color));
        }
        .wrap { padding: 10px 12px 9px; }
        .top { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; min-height:30px; }
        .target-pill {
          display:inline-flex; align-items:baseline; gap:6px; padding:5px 9px; border-radius:999px;
          background:rgba(244,67,54,.11); border:1px solid rgba(244,67,54,.28); white-space:nowrap;
        }
        .target-pill .k { font-size:9px; font-weight:900; letter-spacing:.08em; opacity:.65; }
        .target-pill .v { font-size:14px; font-weight:950; }
        .phase { display:inline-flex; align-items:center; justify-content:flex-end; gap:5px; font-size:10px; font-weight:850; opacity:.82; text-align:right; }
        .phase ha-icon { width:19px; height:19px; }
        .gauge { margin-top:-6px; }
        svg { width:100%; height:126px; display:block; overflow:visible; }
        .base-arc { fill:none; stroke:rgba(127,127,127,.20); stroke-width:16; stroke-linecap:round; }
        .quality-band { fill:none; stroke:rgba(76,175,80,.26); stroke-width:16; }
        .precision-band { fill:none; stroke:rgba(76,175,80,.78); stroke-width:8; }
        .target-marker { stroke:rgb(244,67,54); stroke-width:4; stroke-linecap:round; }
        .needle { stroke-linecap:round; }
        .needle-mash { stroke:var(--primary-text-color); stroke-width:7; opacity:.92; }
        .needle-wort { stroke:rgb(0,188,212); stroke-width:3.2; }
        .hub-outer { fill:var(--primary-text-color); opacity:.92; }
        .hub-inner { fill:rgb(0,188,212); }
        .scale-label { font-size:8px; font-weight:800; fill:var(--secondary-text-color); }
        .center-value { font-size:27px; font-weight:950; fill:var(--primary-text-color); letter-spacing:-.03em; }
        .center-unit { font-size:11px; font-weight:800; fill:var(--secondary-text-color); }
        .title { margin-top:-3px; text-align:center; font-size:13px; font-weight:800; opacity:.78; }
        .readouts { margin-top:5px; display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:6px; }
        .readout { min-width:0; padding:6px 7px; border-radius:11px; background:rgba(127,127,127,.07); border:1px solid rgba(127,127,127,.12); text-align:center; }
        .readout .k { font-size:8px; font-weight:900; letter-spacing:.055em; text-transform:uppercase; opacity:.58; }
        .readout .v { margin-top:1px; font-size:12px; font-weight:950; white-space:nowrap; }
        .mash-dot,.wort-dot { display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:4px; vertical-align:1px; }
        .mash-dot { background:var(--primary-text-color); }
        .wort-dot { background:rgb(0,188,212); }
        .bands { margin-top:5px; text-align:center; font-size:9px; font-weight:760; opacity:.55; }
      </style>

      <ha-card>
        <div class="wrap">
          <div class="top">
            <div class="target-pill">
              <span class="k">TARGET</span>
              <span class="v">${this._fmt(target)} °C</span>
            </div>
            <div class="phase">
              <ha-icon icon="${phase.icon}"></ha-icon>
              <span>${phase.label}</span>
            </div>
          </div>

          <div class="gauge">
            <svg viewBox="0 0 260 132" role="img" aria-label="BrewAssistant temperature gauge">
              <path class="base-arc" d="${basePath}" />
              ${qualityPath ? `<path class="quality-band" d="${qualityPath}" />` : ''}
              ${precisionPath ? `<path class="precision-band" d="${precisionPath}" />` : ''}
              ${targetLine}
              ${line(mashNeedle, 'needle-mash')}
              ${line(wortNeedle, 'needle-wort')}
              <circle class="hub-outer" cx="130" cy="112" r="7" />
              <circle class="hub-inner" cx="130" cy="112" r="3.4" />
              <text class="scale-label" x="28" y="106">${this._fmt(Number(c.min), 0)}</text>
              <text class="scale-label" x="224" y="106">${this._fmt(Number(c.max), 0)}</text>
              <text class="center-value" x="130" y="91" text-anchor="middle">${this._fmt(mash ?? wort)}</text>
              <text class="center-unit" x="130" y="105" text-anchor="middle">${mash !== null ? this._t('Mäsk °C', 'Mash °C') : this._t('Vört °C', 'Wort °C')}</text>
            </svg>
          </div>

          <div class="title">${phase.title}</div>

          <div class="readouts">
            <div class="readout">
              <div class="k"><span class="mash-dot"></span>${this._t('Mäsk', 'Mash')}</div>
              <div class="v">${this._fmt(mash)} °C</div>
            </div>
            <div class="readout">
              <div class="k"><span class="wort-dot"></span>${this._t('Vört', 'Wort')}</div>
              <div class="v">${this._fmt(wort)} °C</div>
            </div>
            <div class="readout">
              <div class="k">Δ ${this._t('Vört–Mäsk', 'Wort–Mash')}</div>
              <div class="v">${this._fmt(delta)} °C</div>
            </div>
          </div>

          <div class="bands">
            ${this._t('precision', 'precision')} ±${this._fmt(Number(c.precision_tolerance))} °C ·
            ${this._t('kvalitetsband', 'quality band')} ±${this._fmt(Number(c.quality_tolerance))} °C
          </div>
        </div>
      </ha-card>
    `;
  }
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, BrewAssistantTemperatureGauge);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
  window.customCards.push({
    type: CARD_TYPE,
    name: 'BrewAssistant Temperature Gauge',
    description: 'BrewAssistant-specific Mash/Wort/Target SVG temperature gauge.',
    preview: true,
    documentationURL: 'https://github.com/Jocke1970/brewassistant-beta',
  });
}

console.info(
  `%c BREWASSISTANT-TEMPERATURE-GAUGE %c ${CARD_VERSION} `,
  'color:white;background:#1976d2;font-weight:700;',
  'color:#1976d2;background:#e3f2fd;'
);