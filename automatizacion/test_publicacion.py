import unittest
from unittest.mock import patch

from automatizacion import editorial, publicar
from automatizacion.comun import config
from automatizacion.reel import bloques, puntuar, tarjeta


class PublicacionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        self.item = {"id": 128, "tipo": "oracion", "turno": "noche", "estado": "pendiente",
                     "texto": "**Señor,** acompáñame hoy.", "tema": "la familia", "hashtags": "#Dios #FE",
                     "oracion": "Señor, acompaña a mi familia. En el nombre de Jesús, amén.",
                     "descripcion": "Una oración para tu familia.\n\n\nSi esta oración es para ti, escribe Amén."}

    def test_hashtags_amplios_minusculas_y_experimento(self):
        self.assertEqual(editorial.hashtags(self.item, self.cfg), ["#dios", "#jesus", "#amen", "#familia", "#fyp"])
        self.item["id"] = 129
        self.assertEqual(editorial.hashtags(self.item, self.cfg)[-1], "#oracion")
        self.assertLessEqual(len(editorial.hashtags(self.item, self.cfg)), 5)

    def test_caption_antigua_sin_espacios_excesivos(self):
        texto = publicar.caption(self.item, self.cfg)
        self.assertNotIn("\n\n\n", texto)
        self.assertNotIn("escribe Amén", texto)
        self.assertIn("#dios #jesus #amen", texto)

    def test_oracion_completa_en_narracion(self):
        self.assertIn(self.item["oracion"], editorial.guion(self.item))

    def test_subtitulos_conservan_signos_del_guion(self):
        palabras = [{"texto": t} for t in ("Señor", "¿Me", "acompañas", "Amén")]
        # Los metadatos reales contienen las palabras sin signos de interrogación.
        palabras[1]["texto"] = "Me"
        self.assertEqual([p["texto"] for p in puntuar(palabras, "Señor, ¿Me acompañas? Amén.")],
                         ["Señor,", "¿Me", "acompañas?", "Amén."])

    def test_duplicados_comparan_caption_completa(self):
        texto = "a" * 90 + " final distinto"
        with patch.object(publicar, "api", return_value={"data": [{"id": "uno", "caption": "a" * 90 + " otro"}]}):
            self.assertIsNone(publicar.ya_publicado("uid", "token", texto))
        with patch.object(publicar, "api", return_value={"data": [{"id": "dos", "caption": texto}]}):
            self.assertEqual(publicar.ya_publicado("uid", "token", texto), "dos")

    def test_error_al_comprobar_duplicados_impide_publicar(self):
        with patch.object(publicar, "api", side_effect=publicar.ErrorIG("sin conexión")):
            with self.assertRaises(publicar.ErrorIG):
                publicar.ya_publicado("uid", "token", "texto")

    def test_cambio_de_cola_cancela_publicacion(self):
        with patch.dict("os.environ", {"IG_TOKEN": "token-prueba"}), \
             patch.object(publicar, "cargar", return_value=[self.item]), \
             patch.object(publicar, "api", return_value={"username": "oraciondebolsillo", "user_id": "uid"}), \
             patch.object(publicar, "esperar_url") as esperar:
            with self.assertRaises(publicar.ErrorIG):
                publicar.publicar("noche", "https://example.com", False, id_preparado=127)
            esperar.assert_not_called()

    def test_bloques_y_tarjetas_en_tres_formatos(self):
        palabras = [{"texto": str(i), "inicio": i / 2, "fin": (i + 1) / 2} for i in range(17)]
        self.assertEqual([len(b) for b in bloques(palabras)], [7, 7, 3])
        for tipo in ("oracion", "reflexion", "versiculo"):
            self.item["tipo"] = tipo
            self.assertEqual(tarjeta(self.item, "Dios también cuida de ti.").size, (720, 1280))


if __name__ == "__main__":
    unittest.main()
