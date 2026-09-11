# voxd

Lokale Spracheingabe mit Selbstkorrektur. Taste drücken, sprechen, der Text steht
im Feld — ohne dass irgendetwas den Rechner verlässt.

Der Unterschied zu anderen Diktierprogrammen: Du darfst Dich mitten im Satz
korrigieren.

| Du sagst | voxd schreibt |
|---|---|
| „…dass das Meeting am **Dienstag** stattfindet. **Nee, Mittwoch.** Mittwoch um drei." | Das Meeting findet am Mittwoch um drei Uhr statt. |
| „Doku fürs Deployment-Skript, **ach nee, streich das**, die Doku für die CI-Pipeline." | Ich brauche die Doku für die CI-Pipeline. |

**Status:** in Entwicklung. Linux läuft, Windows ist gebaut aber ungetestet.

## Aufbau

Zwei Stufen. Die Spracherkennung schreibt wörtlich mit, danach räumt ein lokales
Sprachmodell auf und führt die Selbstkorrekturen aus.

Standard ist **Parakeet TDT 0.6B v3** — auf einem i5-13600KF gemessen 15× Echtzeit
auf dem Prozessor, und selbst auf nur zwei Kernen noch 5×. Keine Grafikkarte nötig.
Wer eine hat, kann auf Whisper large-v3-turbo umstellen.

## Lizenz

MIT
