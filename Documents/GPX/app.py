# Lancement : streamlit run app.py

import streamlit as st
import folium
from streamlit_folium import st_folium
from editeur_gpx import EditeurGPX

st.set_page_config(page_title="Éditeur GPX", layout="wide")
st.title("🗺️ Éditeur de fichiers GPX")

fichier = st.file_uploader("Charge ton fichier GPX", type=["gpx"])

if fichier is not None:
    contenu = fichier.read().decode("utf-8")

    # Initialisation de la session (uniquement si nouveau fichier)
    if st.session_state.get("nom_fichier") != fichier.name:
        st.session_state.editeur = EditeurGPX(contenu)
        st.session_state.nom_fichier = fichier.name
        st.session_state.clics_coupe = []
        st.session_state.dernier_clic = None

        # On crée automatiquement Départ/Arrivée s'il n'y en a pas
        st.session_state.editeur.creer_waypoints_depuis_trace()

        # ✅ Vue de la carte (centre + zoom) mémorisée entre les reruns
        st.session_state.centre_carte = None
        st.session_state.zoom_carte = 13

    editeur = st.session_state.editeur
    points = editeur.get_points()

    if not points:
        st.error("Aucun point trouvé dans ce fichier.")
        st.write("Contenu du GPX :", editeur.diagnostic())
        st.stop()

    waypoints = editeur.get_waypoints()

    # --- Panneau latéral ---
    mode = st.sidebar.radio(
        "Que veux-tu faire ?",
        [ "✂️ Supprimer une portion", 
        "✂️ Couper l'itinéraire",
         "📍 Ajouter un point",
         "✏️ Déplacer un point existant",
         "🎯 Définir le point de départ"]
    )

    st.sidebar.write(f"Nombre de points du tracé : **{len(points)}**")

    # 🐛 DEBUG temporaire : état réel des waypoints dans l'objet
    st.sidebar.markdown("---")
    # st.sidebar.caption("🐛 DEBUG - Waypoints dans l'objet :")
    # st.sidebar.write(
    #     [(i, w.name) for i, w in enumerate(editeur.gpx.waypoints)]
    # )

    if st.sidebar.button("🔄 Rafraîchir la carte"):
        st.rerun()

    st.sidebar.markdown("---")

    if st.sidebar.button("🔄 Réinitialiser les clics de coupe"):
        st.session_state.clics_coupe = []
        st.session_state.dernier_clic = None
        st.rerun()

    # --- Variables selon le mode ---
    nom_nouveau_point = None
    index_a_deplacer = None

    if mode == "📍 Ajouter un point":
        nom_nouveau_point = st.sidebar.selectbox(
            "Type de point à ajouter",
            ["Départ", "Arrivée", "Étape"]
        )
        st.info(f"Clique sur la carte pour ajouter le point "
                f"**{nom_nouveau_point}**.")

    elif mode == "✏️ Déplacer un point existant":
        if waypoints:
            options = {
                f"{nom} (point {idx})": idx
                for idx, lat, lon, nom in waypoints
            }
            choix = st.sidebar.selectbox(
                "Quel point déplacer ?",
                list(options.keys())
            )
            index_a_deplacer = options[choix]
            st.info("Clique sur la carte pour déplacer ce point "
                    "à un nouvel endroit.")

            if st.sidebar.button("🗑️ Supprimer ce point"):
                if editeur.supprimer_waypoint(index_a_deplacer):
                    st.session_state.dernier_clic = None
                    st.success("Point supprimé !")
                    st.rerun()
                else:
                    st.error("Échec de la suppression (index invalide).")
        else:
            st.warning("Aucun point existant à déplacer. "
                       "Ajoute-en un d'abord.")

    elif mode == "✂️ Couper l'itinéraire":
        st.info(f"Clique sur **2 points** du tracé. "
                f"Clics : **{len(st.session_state.clics_coupe)}/2**")
    
    elif mode == "✂️ Supprimer une portion":          # ← NOUVEAU
        st.info(f"Clique sur **2 points** : la portion entre eux "
                f"sera supprimée, le reste sera gardé. "
                f"Clics : **{len(st.session_state.clics_coupe)}/2**")

    elif mode == "🎯 Définir le point de départ":
        st.info("Clique sur le **tracé** pour définir le nouveau "
                "point de départ. Le tracé reste identique, "
                "l'arrivée se calcule automatiquement (boucle).")

    # --- Création de la carte ---
    # ✅ On utilise le centre/zoom mémorisé, sinon le 1er point du tracé
    centre = st.session_state.centre_carte or points[0]
    zoom = st.session_state.zoom_carte

    carte = folium.Map(location=centre, zoom_start=zoom)
    folium.PolyLine(points, color="blue", weight=4).add_to(carte)

    # Clics de coupe
    for i, idx in enumerate(st.session_state.clics_coupe):
        couleur = "green" if i == 0 else "red"
        label = "Coupe 1" if i == 0 else "Coupe 2"
        folium.Marker(points[idx], popup=label,
                      icon=folium.Icon(color=couleur)).add_to(carte)

    # Portion sélectionnée
    if len(st.session_state.clics_coupe) == 2:
        i1, i2 = sorted(st.session_state.clics_coupe)
        portion = points[i1:i2 + 1]
        folium.PolyLine(portion, color="green", weight=6).add_to(carte)

    # Waypoints existants
    for idx, lat, lon, nom in waypoints:
        if (mode == "✏️ Déplacer un point existant"
                and idx == index_a_deplacer):
            icone = folium.Icon(color="purple", icon="screenshot")
            popup = f"➡️ {nom} (à déplacer)"
        else:
            type_wp = editeur.deviner_type_waypoint(nom)
            if type_wp == "depart":
                icone = folium.Icon(color="green", icon="play")
            elif type_wp == "arrivee":
                icone = folium.Icon(color="red", icon="stop")
            else:
                icone = folium.Icon(color="orange", icon="flag")
            popup = nom

        folium.Marker([lat, lon], popup=popup, icon=icone).add_to(carte)

    # --- Affichage de la carte ---
    resultat = st_folium(
        carte,
        width=900,
        height=500,
        returned_objects=["last_clicked"]  # ✅ on n'écoute QUE les clics
    )

    # ✅ On mémorise la position actuelle de la carte (centre + zoom)
    if resultat.get("center"):
        st.session_state.centre_carte = [
            resultat["center"]["lat"],
            resultat["center"]["lng"]
        ]
    if resultat.get("zoom"):
        st.session_state.zoom_carte = resultat["zoom"]

    # --- Gestion du clic ---
    if resultat.get("last_clicked"):
        lat = resultat["last_clicked"]["lat"]
        lon = resultat["last_clicked"]["lng"]
        clic_actuel = (lat, lon)

        # On ne traite le clic que s'il est NOUVEAU
        if clic_actuel != st.session_state.dernier_clic:
            st.session_state.dernier_clic = clic_actuel

            if mode in ("✂️ Couper l'itinéraire",
                        "✂️ Supprimer une portion"):     # ← MODIFIÉ
                idx = editeur.trouver_point_proche(lat, lon)
                if (idx is not None
                        and idx not in st.session_state.clics_coupe):
                    if len(st.session_state.clics_coupe) < 2:
                        st.session_state.clics_coupe.append(idx)
                        st.rerun()

            elif mode == "📍 Ajouter un point":
                editeur.ajouter_waypoint(lat, lon, nom_nouveau_point)
                st.success(f"Point '{nom_nouveau_point}' ajouté ! "
                           f"({lat:.5f}, {lon:.5f})")
                st.rerun()

            elif (mode == "✏️ Déplacer un point existant"
                  and index_a_deplacer is not None):
                editeur.deplacer_waypoint(index_a_deplacer, lat, lon)
                st.success(f"Point déplacé vers ({lat:.5f}, {lon:.5f})")
                st.rerun()

            elif mode == "🎯 Définir le point de départ":
                idx = editeur.trouver_point_proche(lat, lon)
                if idx is not None:
                    editeur.definir_depart_boucle(idx)
                    st.success(f"Départ défini au point {idx} ! "
                               f"La boucle commence maintenant ici. 🔄")
                    st.rerun()
                else:
                    st.warning("Clique plus près du tracé bleu.")

    # --- Appliquer la coupe ---
    if len(st.session_state.clics_coupe) == 2:
        if mode == "✂️ Couper l'itinéraire":
            if st.button("✂️ Appliquer la coupe (garder le milieu)"):
                i1, i2 = st.session_state.clics_coupe
                editeur.couper_itineraire(i1, i2)
                st.session_state.clics_coupe = []
                st.success("Itinéraire coupé ! ✅")
                st.rerun()

        elif mode == "✂️ Supprimer une portion":
            if st.button("✂️ Supprimer cette portion (garder le reste)"):
                i1, i2 = st.session_state.clics_coupe
                editeur.supprimer_portion(i1, i2)
                st.session_state.clics_coupe = []
                st.success("Portion supprimée ! ✅")
                st.rerun()

    # --- Récapitulatif des points enregistrés ---
    if waypoints:
        st.subheader("📌 Points enregistrés")
        for idx, lat, lon, nom in waypoints:
            type_wp = editeur.deviner_type_waypoint(nom)
            emoji = {"depart": "🟢", "arrivee": "🔴", "etape": "🟠"}[type_wp]
            st.write(f"{emoji} **{nom}** : ({lat:.5f}, {lon:.5f})")

    # --- Téléchargement du fichier modifié ---
    st.download_button(
        label="💾 Télécharger le GPX modifié",
        data=editeur.to_xml(),
        file_name="itineraire_modifie.gpx",
        mime="application/gpx+xml"
    )

else:
    st.info("👆 Commence par charger un fichier GPX.")
