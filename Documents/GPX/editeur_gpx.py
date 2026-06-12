import gpxpy
import gpxpy.gpx
from math import radians, sin, cos, sqrt, atan2


class EditeurGPX:
    """Outil pour modifier des fichiers GPX."""

    def __init__(self, contenu_gpx):
        """Charge le GPX depuis une chaîne de texte."""
        self.gpx = gpxpy.parse(contenu_gpx)

    def get_points(self, num_track=0, num_segment=0):
        """Retourne la liste des points (lat, lon).
        Cherche d'abord dans les tracks, puis dans les routes."""

        # 1. On cherche dans les TRACKS
        if self.gpx.tracks:
            try:
                segment = self.gpx.tracks[num_track].segments[num_segment]
                return [(p.latitude, p.longitude) for p in segment.points]
            except IndexError:
                pass

        # 2. Sinon, on cherche dans les ROUTES
        if self.gpx.routes:
            try:
                route = self.gpx.routes[num_track]
                return [(p.latitude, p.longitude) for p in route.points]
            except IndexError:
                pass

        # 3. Aucun point trouvé
        return []

    def get_waypoints(self):
        """Retourne la liste des waypoints avec leur index."""
        return [
            (i, w.latitude, w.longitude, w.name or f"Point {i}")
            for i, w in enumerate(self.gpx.waypoints)
        ]

    def ajouter_waypoint(self, latitude, longitude, nom):
        """Crée un nouveau waypoint."""
        waypoint = gpxpy.gpx.GPXWaypoint(
            latitude=latitude, longitude=longitude, name=nom
        )
        self.gpx.waypoints.append(waypoint)

    def deplacer_waypoint(self, index, latitude, longitude):
        """Modifie la position d'un waypoint existant (par son index)."""
        try:
            self.gpx.waypoints[index].latitude = latitude
            self.gpx.waypoints[index].longitude = longitude
            return True
        except IndexError:
            return False

    def supprimer_waypoint(self, index):
        """Supprime un waypoint par son index."""
        try:
            del self.gpx.waypoints[index]
            return True
        except IndexError:
            return False

    @staticmethod
    def deviner_type_waypoint(nom):
        """Devine si un waypoint est un départ, une arrivée, ou autre.
        Retourne : 'depart', 'arrivee' ou 'etape'."""

        if nom is None:
            return "etape"

        nom_min = nom.lower()

        mots_depart = ["départ", "depart", "début", "debut", "start", "begin"]
        mots_arrivee = ["arrivée", "arrivee", "fin", "end", "finish", "stop"]

        if any(mot in nom_min for mot in mots_depart):
            return "depart"
        if any(mot in nom_min for mot in mots_arrivee):
            return "arrivee"

        return "etape"

    @staticmethod
    def distance_haversine(lat1, lon1, lat2, lon2):
        """Calcule la distance en mètres entre 2 points GPS."""
        R = 6371000  # Rayon de la Terre en mètres
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    def trouver_point_proche(self, lat, lon, num_track=0, num_segment=0):
        """Trouve l'index du point du tracé le plus proche d'un clic."""
        points = self.get_points(num_track, num_segment)
        if not points:
            return None
        distances = [
            self.distance_haversine(lat, lon, p_lat, p_lon)
            for p_lat, p_lon in points
        ]
        return distances.index(min(distances))

    def couper_itineraire(self, index_debut, index_fin,
                          num_track=0, num_segment=0):
        """Garde uniquement la portion entre index_debut et index_fin.
        Fonctionne pour les tracks ET les routes."""
        i1, i2 = sorted([index_debut, index_fin])

        # Cas TRACK
        if self.gpx.tracks:
            try:
                segment = self.gpx.tracks[num_track].segments[num_segment]
                segment.points = segment.points[i1:i2 + 1]
                return True
            except IndexError:
                pass

        # Cas ROUTE
        if self.gpx.routes:
            try:
                route = self.gpx.routes[num_track]
                route.points = route.points[i1:i2 + 1]
                return True
            except IndexError:
                pass

        return False

    def diagnostic(self):
        """Retourne un résumé du contenu du GPX (utile pour déboguer)."""
        return {
            "nb_tracks": len(self.gpx.tracks),
            "nb_routes": len(self.gpx.routes),
            "nb_waypoints": len(self.gpx.waypoints),
            "points_par_track": [
                sum(len(seg.points) for seg in trk.segments)
                for trk in self.gpx.tracks
            ],
            "points_par_route": [
                len(rte.points) for rte in self.gpx.routes
            ],
        }

    def to_xml(self):
        """Retourne le GPX au format XML (pour téléchargement)."""
        return self.gpx.to_xml()

    def creer_waypoints_depuis_trace(self):
        """Crée automatiquement un waypoint Départ (1er point)
        et Arrivée (dernier point) si aucun waypoint n'existe."""
        points = self.get_points()

        if not points:
            return  # Pas de tracé, on ne fait rien

        # On ne crée les waypoints que s'il n'y en a aucun
        if len(self.gpx.waypoints) == 0:
            lat_depart, lon_depart = points[0]
            lat_arrivee, lon_arrivee = points[-1]

            self.ajouter_waypoint(lat_depart, lon_depart, "Départ")
            self.ajouter_waypoint(lat_arrivee, lon_arrivee, "Arrivée")

    def repositionner_waypoint(self, type_point, lat, lon):
        """Déplace le waypoint Départ ou Arrivée vers de
        nouvelles coordonnées."""
        cible = self.deviner_type_waypoint(type_point)

        for wp in self.gpx.waypoints:
            if self.deviner_type_waypoint(wp.name) == cible:
                wp.latitude = lat
                wp.longitude = lon
                return True

        self.ajouter_waypoint(lat, lon, type_point)
        return True


    def definir_depart_boucle(self, index_depart):
        """
        Fait 'tourner' la boucle pour qu'elle commence au point
        d'index donné. Le tracé reste identique (mêmes points,
        même chemin), seul le point de départ change.
        L'arrivée se positionne automatiquement à la fin.

        index_depart : position du nouveau départ dans le tracé
        """
        segment = self.gpx.tracks[0].segments[0]
        points_trkpt = segment.points

        # 🔄 Rotation de la liste : on commence au nouveau départ
        nouveau_trace = (
            points_trkpt[index_depart:] + points_trkpt[:index_depart]
        )
        segment.points = nouveau_trace

        # Nouveau Départ = premier point
        lat_dep = nouveau_trace[0].latitude
        lon_dep = nouveau_trace[0].longitude
        self.repositionner_waypoint("Départ", lat_dep, lon_dep)

        # Nouvelle Arrivée = dernier point (juste avant de reboucler)
        lat_arr = nouveau_trace[-1].latitude
        lon_arr = nouveau_trace[-1].longitude
        self.repositionner_waypoint("Arrivée", lat_arr, lon_arr)

        return True
    
    def supprimer_portion(self, index_debut, index_fin,
                        num_track=0, num_segment=0):
 
        i1, i2 = sorted([index_debut, index_fin])

    # Cas TRACK
        if self.gpx.tracks:
            try:
                segment = self.gpx.tracks[num_track].segments[num_segment]
                segment.points = segment.points[:i1] + segment.points[i2 + 1:]
                return True
            except IndexError:
                pass

        # Cas ROUTE
        if self.gpx.routes:
            try:
                route = self.gpx.routes[num_track]
                route.points = route.points[:i1] + route.points[i2 + 1:]
                return True
            except IndexError:
                pass

        return False

