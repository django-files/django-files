console.debug('latitude:', latitude)
console.debug('longitude:', longitude)

const map = new ol.Map({
    target: 'map',
    layers: [
        new ol.layer.Tile({
            source: new ol.source.OSM(),
        }),
    ],
    view: new ol.View({
        center: ol.proj.fromLonLat([longitude, latitude]),
        zoom: 10,
    }),
})

const marker = new ol.Feature({
    geometry: new ol.geom.Point(ol.proj.fromLonLat([longitude, latitude])),
})

marker.setStyle(
    new ol.style.Style({
        image: new ol.style.Circle({
            radius: 8,
            fill: new ol.style.Fill({ color: 'red' }),
            stroke: new ol.style.Stroke({ color: 'white', width: 2 }),
        }),
    })
)

const vectorSource = new ol.source.Vector({
    features: [marker],
})

const markerLayer = new ol.layer.Vector({
    source: vectorSource,
})

map.addLayer(markerLayer)
