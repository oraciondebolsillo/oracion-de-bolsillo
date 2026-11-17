import copy
import json
import unittest
from unittest.mock import Mock, patch

from automatizacion import generar
from automatizacion.comun import cargar, config


class GeneracionTests(unittest.TestCase):
    def setUp(self):
        self.banco = cargar("banco_versiculos.json")
        oracion = next(c for c in cargar("cola.json") if c.get("oracion"))
        self.propuesta = {
            "tema": "la familia", "frase": oracion["texto"].replace("**", ""),
            "oracion": oracion["oracion"], "parrafo1": "🙏 Una oración para acompañar a tu familia esta noche.",
            "gancho": "Si hoy te preocupa tu familia, reza conmigo.", "portada": "Una oración por tu familia",
            "hashtags": ["#dios", "#jesus", "#amen", "#familia"],
        }
        self.propuesta["destacado"] = self.propuesta["frase"].split()[0]
        self.cola = [{"id": i, "tipo": tipo, "turno": turno, "estado": "pendiente", "texto": f"Texto previo {i}"}
                     for i, tipo, turno in ((1, "versiculo", "manana"), (2, "versiculo", "manana"),
                                            (3, "reflexion", "tarde"), (4, "reflexion", "tarde"),
                                            (5, "oracion", "noche"))]
        self.cfg = config()
        self.cfg["publicaciones_por_semana"] = {"versiculos": 1, "reflexiones": 1, "oraciones": 1}
        self.cfg["semanas_reserva"] = 2

    def leer(self, nombre):
        return copy.deepcopy(self.cola if nombre == "cola.json" else self.banco)

    def test_reponer_solo_el_tipo_que_falta_conserva_historial(self):
        respuesta = json.dumps({"versiculos": [], "reflexiones": [], "oraciones": [self.propuesta]}, ensure_ascii=False)
        with patch.object(generar, "config", return_value=self.cfg), \
             patch.object(generar, "cargar", side_effect=self.leer), \
             patch.object(generar, "llamar_claude", return_value=respuesta) as llamar, \
             patch.object(generar, "guardar") as guardar:
            self.assertEqual(generar.generar(), 0)
            llamar.assert_called_once()
            resultado = guardar.call_args.args[1]
            self.assertEqual(resultado[:-1], self.cola)
            self.assertEqual(resultado[-1]["tipo"], "oracion")
            self.assertEqual(resultado[-1]["id"], 6)
            self.assertIn("gancho", resultado[-1])

    def test_respuesta_malformada_no_modifica_la_cola(self):
        with patch.object(generar, "config", return_value=self.cfg), \
             patch.object(generar, "cargar", side_effect=self.leer), \
             patch.object(generar, "llamar_claude", return_value='{"oraciones": "incorrecto"}'), \
             patch.object(generar, "error"), \
             patch.object(generar, "aviso"), \
             patch.object(generar, "guardar") as guardar:
            self.assertEqual(generar.generar(intentos_max=1), 1)
            guardar.assert_not_called()

    def test_api_solicita_json_estructurado_sin_razonamiento_previo(self):
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "{}"}]}
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "clave-prueba"}), \
             patch.object(generar.requests, "post", return_value=respuesta) as post:
            self.assertEqual(generar.llamar_claude("Guiones de prueba", self.cfg), "{}")
            peticion = post.call_args.kwargs["json"]
            self.assertEqual(peticion["thinking"], {"type": "between_tools"})
            self.assertEqual(peticion["output_config"]["effort"], "low")
            self.assertEqual(peticion["output_config"]["format"]["type"], "json_schema")

    def test_respuesta_vacia_o_truncada_se_rechaza_explicando_el_motivo(self):
        for datos in ({"stop_reason": "max_tokens", "content": []}, {"stop_reason": "end_turn", "content": []}):
            respuesta = Mock(status_code=200)
            respuesta.json.return_value = datos
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "clave-prueba"}), \
                 patch.object(generar.requests, "post", return_value=respuesta):
                with self.assertRaises(ValueError):
                    generar.llamar_claude("Guiones de prueba", self.cfg)


if __name__ == "__main__":
    unittest.main()
