import psycopg2
import cherrypy
import os
import requests as re

# db connection
db_host = 'localhost'
db_name = 'PDT_project'
db_user = 'PDT_user'
db_pass = 'PDT'
db_port = 5432

open_weather_map_key = "ecd012cdf5bf4a7dd2c5f39a928b3bcb"


def connect_to_db(thread_index):
    cherrypy.thread_data.db = psycopg2.connect(
        host=db_host,
        dbname=db_name,
        user=db_user,
        password=db_pass,
        port=db_port)


cherrypy.engine.subscribe('start_thread', connect_to_db)


class MapGenerator(object):
    @cherrypy.expose
    def index(self):
        return open('public/html/index.html')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def closest_lakes(self, longitude, latitude):
        lon = float(longitude)
        lat = float(latitude)
        cursor = cherrypy.thread_data.db.cursor()
        cursor.execute(
            """
            WITH lake_to_city_distance AS (
                SELECT l.osm_id as lake_id, l.name as lake_name, l.way as lake_way,
                    st_asgeojson(st_centroid(st_transform(l.way, 4326))) as position, l.distance,
                    c.name as city_name, c.place, w.wind_speed, w.wind_degrees,
                    ROW_NUMBER() OVER(PARTITION BY l.osm_id ORDER BY st_distance(l.way, c.way) ASC) AS rk
                FROM (
                    SELECT p.osm_id, p.name, p.way, round(st_distance(st_transform(p.way, 4326)::geography, 
                        ST_GeogFromText('SRID=4326;POINT(%s %s)'))::numeric) as distance
                    FROM planet_osm_polygon p 
                    WHERE (p.natural = 'water' AND p.water != 'river' OR p.natural = 'water' AND p.water IS NULL)
                        AND way_area > 550000
                    ORDER BY st_distance(st_transform(p.way, 4326)::geography,
                        ST_GeogFromText('SRID=4326;POINT(%s %s)')) ASC
                    LIMIT 7
                ) as l
                CROSS JOIN (
                    SELECT p.osm_id, p.name, p.place, p.way
                    FROM planet_osm_point p 
                    WHERE p.place in ('city', 'town')
                        AND p.name IS NOT NULL
                ) as c
                JOIN city_weather w ON w.osm_city_id = c.osm_id
            )
            SELECT row_to_json(row)
            FROM (
                SELECT d.lake_id, d.lake_name, d.position, d.city_name, d.place as city_type, d.distance, d.wind_speed, d.wind_degrees
                FROM lake_to_city_distance d
                WHERE d.rk = 1
                ORDER BY d.distance ASC
            ) as row;
            """, (lon, lat, lon, lat))
        results = []
        for row in cursor:
            results.append(row)
        return results

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def lake_search(self, wind=0, highway='false'):
        cursor = cherrypy.thread_data.db.cursor()

        if highway in ['true', '1']:
            cursor.execute(
                """ 
                WITH lake_to_city_distance AS (
                    SELECT l.osm_id as lake_id, l.name as lake_name, l.way as lake_way,
                        st_asgeojson(st_centroid(st_transform(l.way, 4326))) as position,
                        c.name as city_name, c.place, w.wind_speed, w.wind_degrees,
                        ROW_NUMBER() OVER(PARTITION BY l.osm_id ORDER BY st_distance(l.way, c.way) ASC) AS rk
                    FROM (
                        SELECT p.osm_id, p.name, p.water, p.way
                        FROM planet_osm_polygon p 
                        WHERE (p.natural = 'water' AND p.water != 'river' OR p.natural = 'water' AND p.water IS NULL)
                            AND way_area > 550000
                    ) as l
                    CROSS JOIN (
                        SELECT p.osm_id, p.name, p.place, p.way
                        FROM planet_osm_point p 
                        WHERE p.place in ('city', 'town')
                            AND p.name IS NOT NULL
                    ) as c
                    JOIN city_weather w ON w.osm_city_id = c.osm_id
                )
                SELECT row_to_json(row)
                FROM (
                    SELECT d.lake_id, d.lake_name, d.position, d.city_name, d.place as city_type, d.wind_speed, d.wind_degrees
                    FROM lake_to_city_distance d 
                    CROSS JOIN (
                        SELECT p.ref, p.way
                        FROM planet_osm_roads p
                        WHERE p.highway IN ('motorway', 'trunk')
                    ) as h
                    WHERE d.rk = 1 
                        AND st_distance(d.lake_way, h.way) < 10000
                        AND d.wind_speed > %s
                    GROUP BY d.lake_id, d.lake_name, d.position, d.city_name, d.place, d.wind_speed, d.wind_degrees
                ) as row;
                """, (wind,))
        if highway in ['false', '0']:
            cursor.execute(
                """ 
                WITH lake_to_city_distance AS (
                    SELECT l.osm_id as lake_id, l.name as lake_name, l.way as lake_way,
                        st_asgeojson(st_centroid(st_transform(l.way, 4326))) as position,
                        c.name as city_name, c.place, w.wind_speed, w.wind_degrees,
                        ROW_NUMBER() OVER(PARTITION BY l.osm_id ORDER BY st_distance(l.way, c.way) ASC) AS rk
                    FROM (
                        SELECT p.osm_id, p.name, p.water, p.way, st_area(p.way) as area
                        FROM planet_osm_polygon p 
                        WHERE (p.natural = 'water' AND p.water != 'river' OR p.natural = 'water' AND p.water IS NULL)
                            AND way_area > 550000
                    ) as l
                    CROSS JOIN (
                        SELECT p.osm_id, p.name, p.place, p.way
                        FROM planet_osm_point p 
                        WHERE p.place in ('city', 'town')
                            AND p.name IS NOT NULL
                    ) as c
                    JOIN city_weather w ON w.osm_city_id = c.osm_id
                )
                SELECT row_to_json(row)
                FROM (
                    SELECT d.lake_id, d.lake_name, d.position, d.city_name, d.place as city_type, d.wind_speed, d.wind_degrees
                    FROM lake_to_city_distance d
                    WHERE d.rk = 1
                        AND d.wind_speed > %s
                ) as row;
                """, (wind,))
        # if highway in ['true', '1'] and names in ['false', '0']:
        #     cursor.execute(
        #         """
        #         SELECT row_to_json(row)
        #         FROM (
        #             SELECT p.osm_id as lake_id, p.name as lake_name,
        #                 st_asgeojson(st_centroid(st_transform(p.way, 4326))) as position,
        #                 NULL as city_name, NULL as city_type
        #             FROM planet_osm_polygon p
        #             CROSS JOIN (
        #                 SELECT p.ref, p.way
        #                 FROM planet_osm_roads p
        #                 WHERE p.highway IN ('motorway', 'trunk')
        #             ) as h
        #             WHERE (p.natural = 'water' AND p.water != 'river' OR p.natural = 'water' AND p.water IS NULL)
        #                 AND way_area > 550000
        #                 AND st_distance(p.way, h.way) < 10000
        #             GROUP BY p.osm_id, p.name, p.way
        #         ) as row;
        #         """)
        # if highway in ['false', '0'] and names in ['false', '0']:
        #     cursor.execute(
        #         """
        #         SELECT row_to_json(row)
        #         FROM (
        #             SELECT p.osm_id as lake_id, p.name as lake_name,
        #                 st_asgeojson(st_centroid(st_transform(p.way, 4326))) as position,
        #                 NULL as city_name, NULL as city_type
        #             FROM planet_osm_polygon p
        #             WHERE (p.natural = 'water' AND p.water != 'river' OR p.natural = 'water' AND p.water IS NULL)
        #                 AND way_area > 550000
        #         ) as row;
        #         """)
        results = []
        for row in cursor:
            results.append(row)
        return results

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def update_weather(self, reset='false'):
        cursor = cherrypy.thread_data.db.cursor()
        data = []

        if reset in ('true', '1'):
            cursor.execute(
                """
                DELETE FROM city_weather;
                """)
            cursor.execute(
                """
                WITH lake_to_city_distance AS (
                    SELECT l.osm_id as lake_id, l.name as lake_name, 
                        l.water, l.way as lake_way, 
                        c.osm_id as city_id, c.name as city_name, 
                        c.place, c.way as city_way,
                    ROW_NUMBER() OVER(PARTITION BY l.osm_id ORDER BY st_distance(l.way, c.way) ASC) AS rk
                    FROM (
                        SELECT p.osm_id, p.name, p.water, p.way
                        FROM planet_osm_polygon p 
                        WHERE (p.natural = 'water' AND p.water != 'river' OR p.natural = 'water' AND p.water IS NULL)
                            AND way_area > 550000
                    ) as l
                    CROSS JOIN (
                        SELECT p.osm_id, p.name, p.place, p.way
                        FROM planet_osm_point p 
                        WHERE p.place in ('city', 'town')
                        AND p.name IS NOT NULL
                    ) as c
                )
                SELECT DISTINCT d.city_id, ST_Y(st_transform(city_way, 4326)) as lat, 
                    ST_X(st_transform(city_way, 4326)) as lon
                FROM lake_to_city_distance d
                WHERE d.rk = 1;
                """)
        else:
            cursor.execute(
                """
                SELECT p.osm_id as city_id, ST_Y(st_transform(p.way, 4326)) as lat, 
                    ST_X(st_transform(p.way, 4326)) as lon
                FROM city_weather c
                JOIN planet_osm_point p ON c.osm_city_id = p.osm_id;
                """)

        for row in cursor:
            params = "?lat=" + str(row[1]) + "&lon=" + str(row[2]) + "&cnt=1&appid=" + open_weather_map_key
            url = "http://api.openweathermap.org/data/2.5/find" + params
            r = re.get(url)
            json = r.json()

            data.append({"osm_city_id": row[0], "wind_speed": json['list'][0]['wind']['speed'],
                         "wind_degrees": json['list'][0]['wind'].get('deg', 0)})

        if reset in ('true', '1'):
            for row in data:
                cursor.execute(
                    """
                    INSERT INTO city_weather (osm_city_id, wind_speed, wind_degrees)
                    VALUES (%(osm_city_id)s, %(wind_speed)s, %(wind_degrees)s);
                    """, row)
        else:
            for row in data:
                cursor.execute(
                    """
                    UPDATE city_weather SET (osm_city_id, wind_speed, wind_degrees) = (%(osm_city_id)s, %(wind_speed)s, %(wind_degrees)s)
                    WHERE osm_city_id = %(osm_city_id)s;
                    """, row)

        cherrypy.thread_data.db.commit()
        return {'status': 'ok'}


def CORS():
    cherrypy.response.headers["Access-Control-Allow-Origin"] = "*"
    cherrypy.response.headers["Access-Control-Allow-Methods"] = "GET, POST"
    cherrypy.response.headers["Access-Control-Allow-Headers"] = "Content-Type"


if __name__ == '__main__':
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.CORS.on': True,
            'tools.encode.on': True,
            'tools.encode.encoding': 'utf-8',
            'tools.staticdir.root': os.path.abspath(os.getcwd())
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': './public'
        }
    }
    cherrypy.tools.CORS = cherrypy.Tool('before_handler', CORS)
    cherrypy.quickstart(MapGenerator(), '/', conf)
