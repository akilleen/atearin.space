'use strict';

(function () {
  var OSM_TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
  var OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  var DEFAULT_LAT  = 39.5;
  var DEFAULT_LON  = -98.35;
  var DEFAULT_ZOOM = 4;

  // Explicitly set marker image paths for self-hosted Leaflet.
  // Without this, Leaflet tries to auto-detect from the script URL and fails.
  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconUrl:       '/vendor/leaflet/marker-icon.png',
    iconRetinaUrl: '/vendor/leaflet/marker-icon-2x.png',
    shadowUrl:     '/vendor/leaflet/marker-shadow.png',
  });

  function isSameOrigin(url) {
    if (!url) return false;
    if (url.startsWith('//')) return false;
    if (url.startsWith('/') || url.startsWith('./') || url.startsWith('../')) return true;
    try {
      return new URL(url).origin === window.location.origin;
    } catch (e) {
      return false;
    }
  }

  function initMap(container) {
    var kmlUrl = container.dataset.kmlUrl || '';

    if (kmlUrl && !isSameOrigin(kmlUrl)) {
      console.warn('osm-map: KML URL must be same-origin, ignoring:', kmlUrl);
      kmlUrl = '';
    }

    var height = container.dataset.height || '400px';
    container.style.height = height;

    var lat    = parseFloat(container.dataset.lat)          || DEFAULT_LAT;
    var lon    = parseFloat(container.dataset.lon)          || DEFAULT_LON;
    var zoom   = parseInt(container.dataset.zoom, 10) || DEFAULT_ZOOM;

    var map = L.map(container.id).setView([lat, lon], zoom);

    L.tileLayer(OSM_TILE_URL, {
      attribution: OSM_ATTRIBUTION,
      maxZoom: 19,
    }).addTo(map);

    if (kmlUrl) {
      omnivore.kml(kmlUrl)
        .on('ready', function () {
          try {
            var bounds = this.getBounds();
            if (bounds.isValid()) {
              map.fitBounds(bounds);
            }
          } catch (e) {
            // bounds invalid — map stays at default view
          }
        })
        .on('error', function () {
          console.warn('osm-map: failed to load KML from', kmlUrl);
        })
        .addTo(map);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var containers = document.querySelectorAll('.ham-osm-map[id]');
    containers.forEach(initMap);
  });
}());
