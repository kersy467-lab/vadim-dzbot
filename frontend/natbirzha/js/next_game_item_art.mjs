const p = (bright, dark, light, art) => Object.freeze({
  palette: Object.freeze([bright, dark, light]),
  art,
});

const commonStroke = 'stroke="{dark}" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"';

export const NEXT_GAME_ITEM_ART = Object.freeze({
  payment_services: p('#63b6c5', '#27627a', '#e0f7fb', `<rect x="5" y="4" width="14" height="16" rx="2" fill="{light}" ${commonStroke}/><path d="M8 8h8M8 12h4m1 4 2 2 3-4" fill="none" ${commonStroke}/>`),
  credit_services: p('#738cb8', '#344c7b', '#e3eaff', `<path d="M5 3h10l4 4v14H5z" fill="{light}" ${commonStroke}/><path d="M14 3v5h5M8 12h8m-8 3h5" fill="none" ${commonStroke}/><circle cx="16.5" cy="17" r="2" fill="{bright}" ${commonStroke}/>`),
  investment_services: p('#58a989', '#28654e', '#ddf5e8', `<path d="M4 20h16M5 17l4-5 3 2 6-8" fill="none" ${commonStroke}/><path d="M15 6h3v3" fill="none" ${commonStroke}/><rect x="5" y="15" width="2" height="3" rx=".5" fill="{light}" ${commonStroke}/>`),
  district_heat: p('#e59742', '#8b4b23', '#ffedd2', `<path d="M6 5v14m4-14v14m4-14v14m4-14v14M4 7h16M4 17h16" fill="none" ${commonStroke}/><path d="M11 3c-2 2-2 3 0 4m3-4c-2 2-2 3 0 4" fill="none" stroke="{bright}" stroke-width="1.4"/>`),
  reactor_fuel: p('#f0bd3e', '#94651a', '#fff2bd', `<path d="M6 5h3v14H6zm5 0h3v14h-3zm5 0h3v14h-3z" fill="{light}" ${commonStroke}/><path d="M7.5 3v2m5-2v2m5-2v2" fill="none" ${commonStroke}/><circle cx="12" cy="12" r="2" fill="{bright}"/>`),
  storage_capacity: p('#5da9bd', '#2e647b', '#def5fb', `<rect x="3" y="7" width="17" height="11" rx="2" fill="{light}" ${commonStroke}/><path d="M21 10v5M7 10h3v5H7zm5 0h3v5h-3z" fill="{bright}" ${commonStroke}/>`),
  green_hydrogen: p('#76b66b', '#3f7045', '#e6f8dc', `<path d="M9 4h6m-5 0v6l-5 8a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-8V4" fill="{light}" ${commonStroke}/><circle cx="9" cy="16" r="1.2" fill="{bright}"/><circle cx="14.5" cy="14" r="1.2" fill="{bright}"/><path d="m10 16 3.5-2" ${commonStroke}/>`),
  grid_services: p('#edc34a', '#96711f', '#fff3c2', `<path d="m12 3-7 18m7-18 7 18M8 8h8M6.5 12h11M5 16h14M9 8l3 13m3-13-3 13" fill="none" ${commonStroke}/><circle cx="12" cy="3" r="2" fill="{bright}" ${commonStroke}/>`),
  plasma_services: p('#a46cce', '#603d8a', '#f0e2ff', `<circle cx="12" cy="12" r="7" fill="{light}" ${commonStroke}/><path d="M7 13c2-5 8-5 10 0m-9 3c2-3 6-3 8 0" fill="none" stroke="{bright}" stroke-width="1.5"/><circle cx="12" cy="9" r="2" fill="{bright}"/>`),
  hydrogen_services: p('#5cad83', '#326b54', '#dff7e9', `<path d="M7 5h10l1 14H6z" fill="{light}" ${commonStroke}/><path d="M9 5V3h6v2m-5 4h4m-4 4h4m-4 4h4" fill="none" ${commonStroke}/><circle cx="12" cy="11" r="1.2" fill="{bright}"/>`),
  polymer_fiber: p('#b276bd', '#704675', '#f6e4fa', `<path d="M7 5h10l2 14H5z" fill="{light}" ${commonStroke}/><path d="M8 8c2 2 6 2 8 0m-8 3c2 2 6 2 8 0m-8 3c2 2 6 2 8 0" fill="none" stroke="{bright}" stroke-width="1.5"/>`),
  medical_polymer: p('#d17b9a', '#81445e', '#ffe4ef', `<path d="M9 4h6m-5 0v6l-5 8a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-8V4" fill="{light}" ${commonStroke}/><path d="M12 12v5m-2.5-2.5h5" stroke="{bright}" stroke-width="1.8" stroke-linecap="round"/>`),
  carbon_material: p('#87929c', '#424d59', '#e3e9ef', `<path d="m7 5 5-2 5 2 3 5-3 9-5 3-5-3-3-9z" fill="{light}" ${commonStroke}/><path d="m7 5 5 4 5-4m-10 5 5-1 5 1m-10 4 5-4 5 4m-5-4v10" fill="none" ${commonStroke}/>`),
  diagnostics: p('#39a9a4', '#25635f', '#d9f6f0', `<rect x="4" y="5" width="16" height="14" rx="2" fill="{light}" ${commonStroke}/><path d="M7 12h2l1.5-3 2.5 6 1.5-3H17" fill="none" stroke="{bright}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`),
  battery_pack: p('#e2b547', '#876320', '#fff1bf', `<rect x="4" y="6" width="16" height="13" rx="2" fill="{light}" ${commonStroke}/><path d="M8 4v2m8-2v2m-7 4 3-1v5l3-2" fill="none" stroke="{bright}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`),
  habitat_module: p('#6295b4', '#345f79', '#e0f3fb', `<path d="M4 19h16M5 18a7 7 0 0 1 14 0M8 12V9h8v3m-4-3V5m-4 8h8" fill="{light}" ${commonStroke}/><circle cx="9" cy="15" r="1" fill="{bright}"/><circle cx="15" cy="15" r="1" fill="{bright}"/>`),
  cold_capacity: p('#69b9d3', '#346c88', '#e1f8ff', `<path d="M12 3v18m-7-14 14 8M5 15l14-8M9 5l3 2 3-2m-6 14 3-2 3 2m-10-9 3-.5.5-3m12 7-3 .5-.5 3m-12 0 3-.5.5 3m12-10-3 .5-.5-3" fill="none" ${commonStroke}/>`),
  rail_capacity: p('#d87952', '#82412c', '#ffe6d8', `<path d="M6 4h12v11a6 6 0 0 1-12 0z" fill="{light}" ${commonStroke}/><path d="M8 7h3v4H8zm5 0h3v4h-3zm-4 12-2 2m9-2 2 2M7 15h10" fill="none" ${commonStroke}/>`),
  port_capacity: p('#4f9eaf', '#2c5e70', '#ddf6fb', `<path d="M4 14h16l-2 5H7z" fill="{light}" ${commonStroke}/><path d="M12 4v10m-5-8h5M5 12l3-3m11 4-4-4m-9 7c2 2 4 2 6 0s4-2 6 0" fill="none" ${commonStroke}/>`),
  air_capacity: p('#69a4d0', '#385d8b', '#e2f1ff', `<path d="m3 13 8-2V4a1 1 0 0 1 2 0v7l8 2v2l-8-1v4l3 2v1l-4-1-4 1v-1l3-2v-4l-8 1z" fill="{light}" ${commonStroke}/>`),
  warehouse_services: p('#c29b5d', '#705536', '#f8ebca', `<path d="M3 10 12 4l9 6v10H3z" fill="{light}" ${commonStroke}/><path d="M7 12h3v3H7zm7 0h3v3h-3zm-7 5h10" fill="none" ${commonStroke}/>`),
  urban_services: p('#9b7dc1', '#584477', '#eee5fb', `<path d="M3 20V9h5v11m1 0V4h6v16m1 0v-8h5v8z" fill="{light}" ${commonStroke}/><path d="M5 12h1m5-4h2m-2 4h2m-2 4h2m5 0h1" fill="none" ${commonStroke}/>`),
  life_support: p('#5cae9d', '#2f6b60', '#ddf6ee', `<path d="M8 4h8v16H8z" fill="{light}" ${commonStroke}/><path d="M10 4V2h4v2m-2 4v7m-3.5-3.5h7" fill="none" stroke="{bright}" stroke-width="1.5" stroke-linecap="round"/><circle cx="12" cy="16.5" r="1" fill="{bright}"/>`),
  orbital_logistics: p('#756ec0', '#3f3d7a', '#e6e7ff', `<rect x="6" y="7" width="12" height="12" rx="2" fill="{light}" ${commonStroke}/><path d="M3 9V4h5m13 11v5h-5M3 4l5 5m13 10-5-5" fill="none" ${commonStroke}/><circle cx="12" cy="13" r="2" fill="{bright}"/>`),
  vision_system: p('#7189cc', '#394e89', '#e4eaff', `<path d="M3 12s3-6 9-6 9 6 9 6-3 6-9 6-9-6-9-6z" fill="{light}" ${commonStroke}/><circle cx="12" cy="12" r="3" fill="{bright}" ${commonStroke}/><circle cx="12" cy="12" r="1" fill="{light}"/>`),
  security_services: p('#627789', '#344657', '#e2edf4', `<path d="m12 3 8 3v5c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z" fill="{light}" ${commonStroke}/><rect x="9" y="10" width="6" height="5" rx="1" fill="{bright}"/><path d="M10.5 10V8a1.5 1.5 0 0 1 3 0v2" fill="none" ${commonStroke}/>`),
  model_services: p('#8185c9', '#48477e', '#e8e8ff', `<path d="M8 4a3 3 0 0 0-3 3v1a3 3 0 0 0-2 3v3a3 3 0 0 0 2 3v1a3 3 0 0 0 3 3h8a3 3 0 0 0 3-3v-1a3 3 0 0 0 2-3v-3a3 3 0 0 0-2-3V7a3 3 0 0 0-3-3z" fill="{light}" ${commonStroke}/><circle cx="9" cy="11" r="1" fill="{bright}"/><circle cx="15" cy="11" r="1" fill="{bright}"/><path d="M9 15c2 2 4 2 6 0" fill="none" ${commonStroke}/>`),
  engineering_services: p('#cb9a49', '#795626', '#fff0c8', `<circle cx="12" cy="12" r="4" fill="{light}" ${commonStroke}/><path d="m12 3 1 2 2 .5 2-1 2 2-1 2 .5 2 2 1v3l-2 1-.5 2 1 2-2 2-2-1-2 .5-1 2H9l-1-2-2-.5-2 1-2-2 1-2-.5-2-2-1v-3l2-1 .5-2-1-2 2-2 2 1 2-.5 1-2z" fill="none" stroke="{dark}" stroke-width="1"/><circle cx="12" cy="12" r="1.5" fill="{bright}"/>`),
  quantum_services: p('#58b8c7', '#2d697d', '#def8fb', `<ellipse cx="12" cy="12" rx="9" ry="4" fill="none" ${commonStroke}/><ellipse cx="12" cy="12" rx="4" ry="9" fill="none" transform="rotate(45 12 12)" ${commonStroke}/><circle cx="12" cy="12" r="2" fill="{bright}"/><circle cx="19" cy="9" r="1.3" fill="{bright}"/>`),
  insurance_services: p('#69a77d', '#39664a', '#e2f5e6', `<path d="m12 3 8 3v5c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z" fill="{light}" ${commonStroke}/><path d="m9 12 2 2 4-4" fill="none" stroke="{bright}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M8 7h8" fill="none" ${commonStroke}/>`),
  leasing_services: p('#a17ab9', '#59436f', '#efe3f7', `<path d="M4 19h16M6 17V9h12v8M4 9l8-5 8 5" fill="{light}" ${commonStroke}/><path d="M9 12h6m-6 3h6" fill="none" ${commonStroke}/><circle cx="18" cy="6" r="3" fill="{bright}"/>`),
  settlement_services: p('#4ca99c', '#28665e', '#ddf6ef', `<path d="M5 7h13m-3-3 3 3-3 3M19 17H6m3-3-3 3 3 3" fill="none" ${commonStroke}/><rect x="4" y="10" width="6" height="4" rx="1" fill="{light}" ${commonStroke}/><circle cx="16" cy="12" r="2" fill="{bright}"/>`),
  risk_services: p('#c79845', '#755523', '#fff0c5', `<path d="M12 4v15m-7 0h14M5 7h14M7 7l-3 6h6zm10 0-3 6h6z" fill="{light}" ${commonStroke}/><path d="M16 9V5l3-2" fill="none" stroke="{bright}" stroke-width="1.4"/>`),
  custody_services: p('#b3904d', '#65502c', '#f6eccb', `<rect x="4" y="10" width="16" height="10" rx="2" fill="{light}" ${commonStroke}/><path d="M7 10V7a5 5 0 0 1 10 0v3m-5 4v3" fill="none" ${commonStroke}/><circle cx="12" cy="14" r="1.4" fill="{bright}"/>`),
});

export const NEXT_GAME_ITEM_IDS = Object.freeze(Object.keys(NEXT_GAME_ITEM_ART));

export function getNextGameItemArtwork(itemId) {
  return NEXT_GAME_ITEM_ART[String(itemId || '').toLowerCase()] || null;
}
