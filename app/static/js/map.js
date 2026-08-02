import { get } from './api.js';
import { $, escapeHtml, state } from './utils.js';
import * as L from '../vendor/leaflet/dist/leaflet-src.esm.js';

const PLACE_COORDINATES = {
  '감천문화마을': [35.0975, 129.0106], '개금': [35.1530, 129.0200], '경성대·부경대': [35.1370, 129.1000],
  '광안리': [35.1532, 129.1186], '괴정': [35.1000, 128.9930], '구포': [35.2060, 128.9970],
  '금정산': [35.2540, 129.0550], '기장': [35.2440, 129.2220], '남천': [35.1420, 129.1080],
  '남포동': [35.0980, 129.0320], '다대포': [35.0460, 128.9660], '대신': [35.1110, 129.0150],
  '덕천': [35.2100, 129.0050], '동래': [35.2050, 129.0780], '만덕': [35.2130, 129.0360],
  '망미': [35.1710, 129.1050], '명륜': [35.2120, 129.0830], '명지': [35.0950, 128.9020],
  '문현': [35.1390, 129.0670], '반송': [35.2290, 129.1490], '반여': [35.2000, 129.1240],
  '범일': [35.1400, 129.0590], '부곡': [35.2290, 129.0920], '부산대학교': [35.2320, 129.0840],
  '부산역': [35.1150, 129.0410], '사상': [35.1630, 128.9840], '서면': [35.1570, 129.0590],
  '센텀': [35.1690, 129.1310], '송도': [35.0770, 129.0170], '송정': [35.1780, 129.1990],
  '수영': [35.1660, 129.1140], '수정': [35.1300, 129.0400], '신평': [35.0950, 128.9600],
  '안락': [35.1970, 129.0980], '엄궁': [35.1290, 128.9710], '연산동': [35.1860, 129.0810],
  '영도': [35.0910, 129.0680], '온천천': [35.1980, 129.0810], '용호동': [35.1260, 129.1120],
  '일광': [35.2670, 129.2330], '장림': [35.0810, 128.9700], '재송': [35.1850, 129.1250],
  '전포': [35.1530, 129.0650], '정관': [35.3250, 129.1800], '좌동': [35.1740, 129.1750],
  '주례': [35.1500, 129.0050], '토성': [35.1010, 129.0190], '하단': [35.1060, 128.9660],
  '해운대': [35.1590, 129.1610], '화명': [35.2350, 129.0130],
};

let townMap = null;
let markerLayer = null;
let districtLayer = null;
let contextLayer = null;
let latestStatuses = [];
let districtBounds = null;
const BUSAN_CENTER = [35.1796, 129.0756];
const BUSAN_ZOOM = 11;
const DISTRICT_META = {
  '강서구': { color:'#d7b98d', places:['명지'] },
  '사하구': { color:'#d39a7c', places:['감천문화마을','괴정','다대포','신평','장림','하단'] },
  '서구': { color:'#d6aa75', places:['대신','송도','토성'] },
  '중구': { color:'#c89572', places:['남포동'] },
  '영도구': { color:'#8eb0aa', places:['영도'] },
  '동구': { color:'#c9a27c', places:['범일','부산역','수정'] },
  '남구': { color:'#d6b18d', places:['경성대·부경대','문현','용호동'] },
  '수영구': { color:'#82aba4', places:['광안리','남천','망미','수영'] },
  '해운대구': { color:'#7fa7a2', places:['반송','반여','센텀','송정','재송','좌동','해운대'] },
  '부산진구': { color:'#c8a06e', places:['개금','서면','전포'] },
  '사상구': { color:'#bea47d', places:['사상','엄궁','주례'] },
  '북구': { color:'#9caf85', places:['구포','덕천','만덕','화명'] },
  '동래구': { color:'#a7b78d', places:['동래','명륜','안락'] },
  '연제구': { color:'#b1b98c', places:['연산동','온천천'] },
  '금정구': { color:'#91aa82', places:['부곡','부산대학교','금정산'] },
  '기장군': { color:'#8faf8e', places:['기장','일광','정관'] },
};
let districtGeoData = null;
let contextGeoData = null;

function markerState(status) {
  if (status.latest_card_id) return 'published';
  if (status.distinct_contributors > 0) return 'waiting';
  return 'empty';
}

function markerIcon(status) {
  const kind = markerState(status);
  const count = Number(status.distinct_contributors || 0);
  const label = kind === 'empty' ? '' : `<span>${count > 99 ? '99+' : count}</span>`;
  return L.divIcon({
    className: `memory-map-marker ${kind}`,
    html: `<div>${label}</div>`,
    iconSize: kind === 'empty' ? [14, 14] : [38, 46],
    iconAnchor: kind === 'empty' ? [7, 7] : [19, 43],
    popupAnchor: kind === 'empty' ? [0, -7] : [0, -42],
  });
}

function popupMarkup(status) {
  const progress = status.latest_card_id ? status.new_contributors : status.distinct_contributors;
  const stateText = status.latest_card_id
    ? `동네 카드 발행됨 · 새 참여자 ${progress}/${status.minimum_required}명`
    : status.distinct_contributors
      ? `첫 카드까지 ${progress}/${status.minimum_required}명`
      : '아직 공유된 기억이 없어요';
  const kind = markerState(status);
  const badge = kind === 'published' ? '동네 카드 발행' : (kind === 'waiting' ? '기억이 모이는 중' : '첫 기억을 기다려요');
  return `<div class="map-popup"><small class="${kind}">${badge}</small><b>${escapeHtml(status.place_tag)}</b><span>${escapeHtml(stateText)}</span><button type="button" data-map-place="${escapeHtml(status.place_tag)}">${status.latest_card_id ? '동네 카드 보기' : '이 동네 살펴보기'} <i>→</i></button></div>`;
}

function renderSummary(statuses) {
  const places = statuses.length;
  const active = statuses.filter((item) => Number(item.distinct_contributors || 0) > 0).length;
  const published = statuses.filter((item) => item.latest_card_id).length;
  const contributors = statuses.reduce((sum, item) => sum + Number(item.distinct_contributors || 0), 0);
  $('#townMapSummary').innerHTML = `<span><b>${places}</b>개 장소</span><span><b>${active}</b>곳에 기억</span><span><b>${published}</b>장 발행</span><span><b>${contributors}</b>명 참여</span>`;
}

function districtMemoryCount(district) {
  return latestStatuses
    .filter((status) => district.places.includes(status.place_tag))
    .reduce((sum, status) => sum + Number(status.distinct_contributors || 0), 0);
}

function districtPlaceCount(district) {
  return latestStatuses.filter((status) => district.places.includes(status.place_tag) && Number(status.distinct_contributors || 0) > 0).length;
}

async function renderDistricts() {
  if (!districtLayer || !contextLayer) return;
  if (!contextGeoData) {
    const response = await fetch('/demo/assets/busan-neighbors.geojson?v=2018-kostat');
    if (!response.ok) throw new Error('부산 인접 지역 경계 데이터를 불러오지 못했습니다.');
    contextGeoData = await response.json();
  }
  if (!districtGeoData) {
    const response = await fetch('/demo/assets/busan-districts.geojson?v=2018-kostat');
    if (!response.ok) throw new Error('부산 구·군 경계 데이터를 불러오지 못했습니다.');
    districtGeoData = await response.json();
  }
  contextLayer.clearLayers();
  L.geoJSON(contextGeoData, {
    pane: 'contextPane',
    interactive: false,
    style: {
      color: '#d4cbbb',
      weight: 1.4,
      opacity: 0.75,
      fillColor: '#e7e0d2',
      fillOpacity: 0.82,
      className: 'map-neighbor-region',
    },
  }).addTo(contextLayer);
  districtLayer.clearLayers();
  const geoLayer = L.geoJSON(districtGeoData, {
    pane: 'districtPane',
    style: (feature) => {
      const district = DISTRICT_META[feature.properties.name];
      const memories = district ? districtMemoryCount(district) : 0;
      return {
        color: '#fff9ed', weight: 2.4, opacity: 0.98,
        fillColor: district?.color || '#c8b99e', fillOpacity: memories ? 0.84 : 0.74,
        className: `memory-district ${memories ? 'has-memory' : ''}`,
      };
    },
    onEachFeature: (feature, polygon) => {
      const name = feature.properties.name;
      const district = DISTRICT_META[name] || { places: [] };
      const memories = districtMemoryCount(district);
      const activePlaces = districtPlaceCount(district);
      polygon.bindTooltip(
        `<div class="district-tooltip"><b>${name}</b><span>${activePlaces ? `${activePlaces}곳 · ${memories}명의 기억` : '아직 모인 기억이 없어요'}</span></div>`,
        { sticky: true, direction: 'top', className: 'memory-district-tooltip', opacity: 1 },
      );
      polygon.on('mouseover', () => polygon.setStyle({ fillOpacity: 0.94, weight: 3.6, color: '#fffdf8' }));
      polygon.on('mouseout', () => polygon.setStyle({ fillOpacity: memories ? 0.84 : 0.74, weight: 2.4, color: '#fff9ed' }));
      polygon.on('click', () => townMap.flyToBounds(polygon.getBounds().pad(0.18), { duration: 0.65, maxZoom: 14 }));
    },
  }).addTo(districtLayer);
  districtBounds = geoLayer.getBounds();
  townMap.fitBounds(districtBounds, { padding: [18, 18], animate: false, maxZoom: BUSAN_ZOOM });
  geoLayer.eachLayer((polygon) => {
    const name = polygon.feature?.properties?.name;
    if (!name) return;
    L.marker(polygon.getBounds().getCenter(), {
      pane: 'districtPane',
      interactive: false,
      keyboard: false,
      icon: L.divIcon({
        className: 'district-name-marker',
        html: `<span>${escapeHtml(name)}</span>`,
        iconSize: [64, 18],
        iconAnchor: [32, 9],
      }),
    }).addTo(districtLayer);
  });
}

function selectPlace(place) {
  const input = $('#townPlace');
  input.value = place;
  input.dispatchEvent(new Event('change', { bubbles: true }));
  document.querySelector('.town-controls')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

export function initTownMap() {
  if (townMap || !$('#townMap')) return;
  if (!L) {
    $('#townMap').classList.add('hidden');
    $('#townMapFallback').classList.remove('hidden');
    return;
  }
  townMap = L.map('townMap', {
    scrollWheelZoom: false,
    zoomControl: false,
    minZoom: 10,
    maxZoom: 14,
    attributionControl: false,
  }).setView(BUSAN_CENTER, BUSAN_ZOOM);
  L.control.zoom({ position: 'bottomright', zoomInTitle: '확대', zoomOutTitle: '축소' }).addTo(townMap);
  townMap.createPane('contextPane');
  townMap.getPane('contextPane').style.zIndex = 420;
  townMap.createPane('districtPane');
  // Keep district boundaries below place markers and interaction overlays.
  townMap.getPane('districtPane').style.zIndex = 450;
  contextLayer = L.layerGroup().addTo(townMap);
  districtLayer = L.layerGroup().addTo(townMap);
  markerLayer = L.layerGroup().addTo(townMap);
  $('#townMap').addEventListener('click', (event) => {
    const button = event.target.closest('[data-map-place]');
    if (button) selectPlace(button.dataset.mapPlace);
  });
  $('#resetTownMap')?.addEventListener('click', () => {
    townMap.closePopup();
    if (districtBounds) townMap.flyToBounds(districtBounds, { padding: [18, 18], duration: 0.65, maxZoom: BUSAN_ZOOM });
    else townMap.flyTo(BUSAN_CENTER, BUSAN_ZOOM, { duration: 0.65 });
  });
}

export async function loadTownMap() {
  initTownMap();
  if (!townMap || !markerLayer) return;
  townMap.invalidateSize();
  try {
    const statuses = await get('/archive/places/statuses');
    latestStatuses = statuses;
    markerLayer.clearLayers();
    renderSummary(statuses);
    await renderDistricts();
    statuses.forEach((status) => {
      const coordinates = PLACE_COORDINATES[status.place_tag];
      if (!coordinates || !state.placeTags.includes(status.place_tag)) return;
      L.marker(coordinates, { icon: markerIcon(status), riseOnHover: true, keyboard: true, title: status.place_tag })
        .bindTooltip(status.place_tag, { direction: 'top', offset: [0, -34], className: 'memory-map-tooltip' })
        .bindPopup(popupMarkup(status), { closeButton: true, minWidth: 190, maxWidth: 240 })
        .addTo(markerLayer);
    });
    $('#townMapFallback').classList.add('hidden');
  } catch (error) {
    $('#townMapSummary').innerHTML = '<span>현황을 불러오지 못했어요</span>';
    $('#townMapFallback').textContent = `지도 상태를 불러오지 못했어요. ${error.message}`;
    $('#townMapFallback').classList.remove('hidden');
  }
}
