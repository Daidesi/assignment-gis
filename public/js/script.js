
var layers = [];
var markers = [];
var loader = document.getElementById('loader');
var small_loader = document.getElementById('small_loader');
var lakes_table_body = document.getElementById('closest_lakes_table_body');

mapboxgl.accessToken = 'pk.eyJ1IjoiZGFpZGVzaSIsImEiOiJjam5nYjJyMHgwMTdzM2txZnduNnhhNHdrIn0.6fU_PGh_UuwzKWfL21CRow';
var map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/daidesi/cjninfxui2s292spmuso784yy',
    center: [19.728062, 48.654221],
    zoom: 7.5
});

document.getElementById("map_search").addEventListener("click", function(){
    search(document.getElementById('minimum_wind_speed').value,
        document.getElementById('near_highway').checked);
});

map.on('style.load', function () {
    search('0', false);
});

map.on('click', function(e) {
    if (map.queryRenderedFeatures(e.point)[0].layer.id != 'lakes') {
        clear_markers();
        add_marker(e.lngLat);
        find_closest_lakes(e.lngLat.lat, e.lngLat.lng);
    }
});

function add_marker(longLat) {
    var el = document.createElement('div');
    el.id = 'wut';
    el.classList.add("lake-marker");
    var marker = new mapboxgl.Marker(el)
        .setLngLat(longLat);
    markers.push(marker);
    marker.addTo(map);
}

function clear_markers() {
    markers.forEach(function(marker) {
        marker.remove();
    });
    markers = [];
}

function find_closest_lakes(lat, lng) {
    small_loader.style.display = "block";
    var params = "longitude=" + lng.toString() + "&latitude=" + lat.toString();

    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            var response = JSON.parse(xhttp.responseText);
            replace_table_content(response);
            small_loader.style.display = "none";
        }
    };
    xhttp.open("GET", "http://127.0.0.1:8080/closest_lakes?" + params, true);
    xhttp.send(null);
}

function replace_table_content(response) {
    var new_tbody = document.createElement('tbody');
    new_tbody.id = "closest_lakes_table_body";
    populate_with_new_rows(new_tbody, response);
    lakes_table_body.parentNode.replaceChild(new_tbody, lakes_table_body);
    lakes_table_body = new_tbody;
}

function populate_with_new_rows(new_tbody, response) {
    var row_count = response.length;
    for (var i = 0; i < row_count; i++) {
        var newRow = new_tbody.insertRow(new_tbody.rows.length);
        var cell_name = newRow.insertCell(0);
        var cell_distance = newRow.insertCell(1);
        var cell_wind = newRow.insertCell(2);

        cell_name.innerHTML = "";

        if (response[i][0].lake_name != null) {
            cell_name.innerHTML = response[i][0].lake_name;
        }
        else {
            var lng = Math.round((JSON.parse(response[i][0].position)).coordinates[0] * 10000) / 10000;
            var lat = Math.round((JSON.parse(response[i][0].position)).coordinates[1] * 10000) / 10000;
            cell_name.innerHTML = lat.toString() + ", " + lng.toString();
        }

        cell_distance.innerHTML = response[i][0].distance;
        cell_wind.innerHTML = response[i][0].wind_speed;

        newRow.setAttribute("position", (JSON.parse(response[i][0].position)).coordinates.toString());
        newRow.addEventListener("click", function(){
            fly_to_position(this.getAttribute("position"));
        });
    }
}

function fly_to_position(position) {
    var longLat = position.split(",");
    map.flyTo({center: longLat, zoom: 11});
}


function search(minimum_wind_speed, highway) {
    loader.style.display = "block";
    var wind_speed = "0";
    if (minimum_wind_speed != "") {
        wind_speed = minimum_wind_speed
    }
    var params = "wind=" + wind_speed + "&highway=" + highway.toString();

    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            var response = JSON.parse(xhttp.responseText);
            draw_markers(response);
            loader.style.display = "none";
        }
    };
    xhttp.open("GET", "http://127.0.0.1:8080/lake_search?" + params, true);
    xhttp.send(null);
}

function draw_markers(response) {
    clear_markers_from_layers();
    var features = [];
    var marker_count = response.length;
    for (var i = 0; i < marker_count; i++) {
        var geoJSON = (JSON.parse(response[i][0].position));
        var popup = create_popup_message(response[i][0]);
        features.push([geoJSON, popup])
    }
    create_lake_layer(features);
}

function clear_markers_from_layers() {
    layers.forEach(function(layer) {
        map.removeLayer(layer.id);
        map.removeSource(layer.id);
    });
    layers = [];
}

function create_popup_message(response_row) {
    var name = '';
    if (response_row.lake_name != null) {
        name = '<h6 class="text-center"><b>Lake : </b>' + response_row.lake_name + '</h6>';
    }
    var town = '';
    if (response_row.city_name != null) {
        town = '<p><b>Weather from ' + response_row.city_type + ' : </b>' + response_row.city_name + '</p>';
    }
    var position = '<p><b>Longitude & latitude : </b>' + (JSON.parse(response_row.position)).coordinates + '</p>';
    var wind_speed = '<p><b>Wind speed : </b>' + response_row.wind_speed + ' m/s </p>';
    var wind_degrees = '<p><b>Wind degrees : </b>' + response_row.wind_degrees + ' (' + degrees_to_direction(response_row.wind_degrees) + ')</p>';
    return name + town + position + wind_speed + wind_degrees;
}

function degrees_to_direction(degrees) {
    var value = Math.trunc((degrees / 22.5) + 0.5);
    var direction_array = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
    return direction_array[(value % 16)];
}

function create_lake_layer(raw_features) {
    var features = [];
    raw_features.forEach(function (feature) {
        features.push({
            "type": "Feature",
            'geometry': feature[0],
            'properties': {
                'description': feature[1],
                'icon': 'triangle'
            }
        })
    });

    var layer = {
        'id': 'lakes',
        'type': 'symbol',
        'source': {
            'type': 'geojson',
            'data': {
                'type': 'FeatureCollection',
                'features': features
            }
        },
        'layout': {
            'icon-image': '{icon}-15'
        }
    };

    layers.push(layer);
    map.addLayer(layer);
}

map.on('click', 'lakes', function (e) {
    var coordinates = e.features[0].geometry.coordinates.slice();
    var description = e.features[0].properties.description;

    // Ensure that if the map is zoomed out such that multiple
    // copies of the feature are visible, the popup appears
    // over the copy being pointed to.
    while (Math.abs(e.lngLat.lng - coordinates[0]) > 180) {
        coordinates[0] += e.lngLat.lng > coordinates[0] ? 360 : -360;
    }

    new mapboxgl.Popup()
        .setLngLat(coordinates)
        .setHTML(description)
        .addTo(map);
});

// Change the cursor to a pointer when the mouse is over the places layer.
map.on('mouseenter', 'lakes', function () {
    map.getCanvas().style.cursor = 'pointer';
});

// Change it back to a pointer when it leaves.
map.on('mouseleave', 'lakes', function () {
    map.getCanvas().style.cursor = '';
});