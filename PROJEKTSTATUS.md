# 90-Tage-Challenge PWA — Projektstatus

**Stand:** 2026-06-08  
**Live-URL:** https://muehle79.github.io/90T/  
**Repository:** https://github.com/muehle79/90T (Branch: main)  
**Aktuelle Version:** `1.4.0` (Konstante `APP_VERSION` in index.html)  
**Letzter Commit:** `feat: Kalorien-Statistiken und -Chart im Fortschritt-Screen`

---

## Versionshistorie

| Version | Commit | Inhalt |
|---|---|---|
| 1.0.x | `8038f32` | Initiale Builds, URL-Import (iOS Kurzbefehl), Locale-Fix |
| 1.1.0 | `05d6a68` | 4 Bug-Fixes: Foto-Upload, Check-Tage, Kalender-Dots, PWA-Export/Import |
| 1.2.0 | `dc9617a` | 4 Features: Gewichts-Chart, Foto-Vergleich, Export-Reminder, Notifications |
| 1.2.1 | `8b5c4b0` | Hotfix: doppeltes `const cfg` in `renderSettings()` — App startete nicht |
| 1.2.2 | `151a150` + `80c3458` | Hotfix: iOS Notifications via `SW.showNotification()`, App-Versionierung |
| 1.3.0 | `tbd` | Feat: Makro-basierte Kalorienberechnung & wöchentliche Zielwert-Anpassungen |
| 1.3.1 | `tbd` | Feat: Historische Zielwerte (Anpassungen gelten nur für zukünftige Wochen) |
| 1.4.0 | `tbd` | Feat: Kalorien-Statistiken (Gesamt-Ø, Wochen-Ø) + Kalorienverlauf-Chart im Fortschritt-Screen |

> **Regel:** Bei jeder Änderung `APP_VERSION` in `index.html` erhöhen + `PROJEKTSTATUS.md` mit committen.

---

## Projektbeschreibung

Single-file PWA als persönliches Tagebuch für die 90-Tage-Challenge. Basiert auf dem 90TC_Workbook.pdf (S. 70–180). Kein Framework, kein Backend — alle Daten im `localStorage`. Deployment via GitHub Pages (automatisch bei Push auf `main`, ca. 30–60 Sek.).

**Dateien im Repo:**

| Datei | Zweck |
|---|---|
| `index.html` | Komplette App — HTML + CSS + JS in einer Datei (minifiziert) |
| `manifest.json` | PWA-Manifest für Home-Screen-Installation |
| `sw.js` | Service Worker — Offline-Cache + Notification-Click-Handler |
| `icon-192.png` / `icon-512.png` | App-Icons |
| `import.html` | Hilfsseite für URL-basierten Daten-Import (iOS Kurzbefehl) |
| `PROJEKTSTATUS.md` | Diese Datei — wird bei jeder Änderung mit committet |

---

## Technische Architektur

| Schicht | Details |
|---|---|
| Storage | `localStorage` mit Prefix `90tc_` (Wrapper: `S.get/set/del/clear`) |
| Foto-Speicherung | Base64-kodiert, komprimiert via Canvas (max 900px, JPEG 72%) |
| Routing | `App.showScreen(name)` — kein URL-Routing, `back()` via `_prevScreen` |
| Offline | Service Worker cached `index.html`, `manifest.json`, Icons |
| Notifications | `serviceWorker.ready.then(reg => reg.showNotification(...))` — iOS-kompatibel |
| URL-Import | `?import&date=YYYY-MM-DD&weight=X&kal=X&pro=X&fat=X&kh=X&steps=X&sleep=X` |

**localStorage-Keys:**

| Key | Inhalt |
|---|---|
| `settings` | Startdatum, Name, Zielwerte, Reminder-Config |
| `statusQuo` | Gewicht, KFA, Umfänge, Vorher-Fotos (Base64) |
| `daily_YYYY-MM-DD` | Tageseintrag (Gewicht, Macros, Training, Texte) |
| `weekly_N` | Wochencheck N (Umfänge) |
| `monthly_N` | Monatscheck N (Umfänge, Kalorienanpassung) |
| `final` | Abschlussauswertung (Umfänge, Nachher-Fotos) |
| `lastExport` | Timestamp letzter Daten-Export (für Reminder) |
| `notifShown_YYYY-MM-DD` | Verhindert mehrfache Notification pro Tag |

**Settings-Objekt-Schema:**
```json
{
  "startDate": "YYYY-MM-DD",
  "name": "string",
  "targets": {
    "kalorien": 1950, "protein": 120, "fett": 65,
    "kh": 236, "schlaf": 8, "schritte": 10000, "wasser": 2.5
  },
  "reminder": { "enabled": true, "time": "20:00" }
}
```

**Tag-Typen (`checkType(dayN)`):**
- `daily` — Tage 1–90 (außer Check-Tage)
- `weekly` — Tag 7, 14, 21, 35, 42, 49, 63, 70, 77
- `monthly` — Tag 28, 56
- `final` — Tag 90

---

## Screens-Übersicht

| Screen-ID | Zweck | Erreichbar via |
|---|---|---|
| `screen-splash` | Startscreen / Onboarding | App-Start ohne Settings |
| `screen-setup` | 3-Schritt-Wizard Ersteinrichtung | Splash |
| `screen-calendar` | Kalender + Statistiken | Nav-Bar |
| `screen-entry` | Tageseintrag | Kalender-Tag, Nav "Heute" |
| `screen-weekly` | Wöchentlicher Check | Entry-Banner an Check-Tagen |
| `screen-monthly` | Monatlicher Check | Entry-Banner an Check-Tagen |
| `screen-final` | Tag-90 Abschlussauswertung | Entry-Banner Tag 90 |
| `screen-statusquo` | Status Quo bearbeiten | Einstellungen |
| `screen-chart` | SVG Gewichtsverlauf-Chart | Kalender → "📊 Fortschritt" |
| `screen-fotocompare` | Vorher/Nachher Vergleich | Abschluss-Screen, Einstellungen |
| `screen-settings` | Einstellungen + Datensicherung + Notifications | Nav-Bar |

---

## Alle behobenen Bugs

| Version | # | Bug | Fix |
|---|---|---|---|
| <1.1 | 1 | Splash-Screen immer sichtbar | `.active`-Selektor korrigiert |
| <1.1 | 2 | Umfänge-Felder abgeschnitten | Flex statt Grid |
| <1.1 | 3 | Kalender zeigt Vortag | `toISOString()` → lokale Datumsfunktion |
| <1.1 | 4 | URL-Import trägt keine Werte ein | Dezimalkomma-Konvertierung `_cv()` |
| 1.1.0 | 5 | Fotos aus Fotorolle nicht wählbar | `capture="camera"` entfernt |
| 1.1.0 | 6 | Tageseintrag an Check-Tagen blockiert | `openDay()` → immer `openEntry()` + Check-Banner |
| 1.1.0 | 7 | Kalender-Dots unsichtbar | CSS: `.cal-day-dot.done/.partial` |
| 1.1.0 | 8 | PWA startet ohne Daten | iOS-Design → Export/Import-Workaround |
| 1.2.1 | 9 | App startet nicht (weiße Seite) | Doppeltes `const cfg` in `renderSettings()` |
| 1.2.2 | 10 | Notifications trotz Berechtigung stumm | `new Notification()` → `SW.showNotification()` |

---

## Alle implementierten Features

### Kern (aus Workbook)
- Tägliches Tracking: Gewicht, Kalorien/Protein/Fett/KH, Schlaf, Schritte, Wasser
- Krafttraining-Toggles (Geplant / Durchgeführt / Progression)
- Freitexte: "3 Dinge die gut liefen", "3 Dinge für heute"
- Fortschritts-Balken Soll/Ist für alle Felder
- Wöchentliche + monatliche Checks mit Umfangsmessungen (10 Körperstellen)
- Abschluss-Auswertung Tag 90
- 90 Motivationszitate (einer pro Tag)

### Kalender & Navigation
- Monatskalender mit Vor/Zurück
- Status-Dots: 🟢 vollständig · 🟡 teilweise · 🟠 Check offen · 🔵 Check erledigt
- An Check-Tagen: immer zuerst Tageseintrag, dann Banner "Zum Check →"

### Foto-System
- Vorher + Nachher-Fotos (vorn / hinten / seitlich)
- Kamera und Fotorolle wählbar

### Datensicherung & Import
- URL-Parameter-Import (iOS Kurzbefehl)
- JSON-Export (alles kopierbar) + JSON-Import (Paste & Reload)
- Export-Reminder-Banner nach 7 Tagen ohne Sicherung

### Gewichtsverlauf-Chart
- SVG-basiert, keine externe Library, offline-fähig
- Tägliche Punkte + 7-Tage gleitender Durchschnitt
- Statistik-Bar: Start / Aktuell / Delta / Messtage

### Vorher/Nachher Foto-Vergleich
- 3 Zeilen × 2 Spalten (Vorher | Nachher)
- Erreichbar aus Abschluss-Screen und Einstellungen

### Tägliche Erinnerung (Web Notifications)
- Konfigurierbar: Checkbox + Uhrzeit in Einstellungen
- Auslieferung via `ServiceWorkerRegistration.showNotification()` (iOS-kompatibel)
- Tippen auf Notification → App öffnet sich
- **Voraussetzung iOS:** Installierte PWA (Home-Screen), iOS 16.4+

### App-Versionierung
- `APP_VERSION` Konstante oben im JS
- Kleine Anzeige ganz unten im Einstellungsmenü

---

## iOS Kurzbefehl (URL-Import)

```
https://muehle79.github.io/90T/?import&date=YYYY-MM-DD&weight=75.3&kal=2100&pro=150&fat=70&kh=220&steps=8500&sleep=7.5
```

Manuell auf dem Gerät erstellt (unsigned `.shortcut` werden von iOS blockiert).  
Quellen: Happy Scale + StepsApp → Apple Health | FDDB → manuell.

---

## Bekannte Einschränkungen

| Einschränkung | Workaround |
|---|---|
| localStorage ~5 MB Limit | Fotos sparsam einsetzen |
| iOS PWA ≠ Safari localStorage | Export aus Safari → Import in PWA |
| iOS löscht PWA-Storage bei Inaktivität | Regelmäßig exportieren |
| Notifications nur in installierter PWA | In Safari: kein Support |

---

## Für andere KI-Agenten: Schnellreferenz

**Stack:** Einzelne `index.html`, minifiziertes JS, kein Build-Step, kein Framework.

**Zentrale Objekte:**
- `App = { ... }` — alle UI-Methoden
- `S = { get, set, del, clear }` — localStorage-Wrapper mit `90tc_`-Prefix
- `APP_VERSION` — Versionsstring, bei jeder Änderung erhöhen
- `QUOTES[89]` — Motivationszitate (Index = Tag-1)
- `MEASUREMENTS[]` — Umfang-Felder `{k, l}`

**Wichtige Hilfsfunktionen:**
```
parseDate(str)       → Date
dateStr(date)        → 'YYYY-MM-DD'
dayNumber(dateS)     → 1–90 | null
checkType(dayN)      → 'daily'|'weekly'|'monthly'|'final'
weekNum(dn)          → 1–9
monthNum(dn)         → 1–2
addDays(date, n)     → Date
movingAvg(dateS)     → string (7-Tage-Schnitt) | null
toast(msg, ms)       → Toast-Benachrichtigung
progColor(pct)       → 'green'|'yellow'|'red'
```

**Workflow für Änderungen:**
```bash
# Repo klonen (frische Session):
git clone https://muehle79:[PAT]@github.com/muehle79/90T.git /tmp/90t-repo

# Nach Änderungen:
# 1. APP_VERSION in index.html erhöhen
# 2. PROJEKTSTATUS.md aktualisieren
# 3. JS validieren:
node -e "const h=require('fs').readFileSync('index.html','utf8');
  new Function(h.slice(h.indexOf('<script>')+8,h.lastIndexOf('</script>')));
  console.log('OK')"
# 4. Committen & pushen:
git add index.html sw.js PROJEKTSTATUS.md
git commit -m "..."
git push origin main
```

PAT: im Memory-System der KI gespeichert (memory/project_90tc.md).
