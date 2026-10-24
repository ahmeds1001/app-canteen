# OVAGRI Groupe — brand guide for the canteen app

Source: the company logo (`ovagri-logo.png` in this folder). Colours were sampled from the logo, then
darkened where needed so text meets WCAG 2.1 AA contrast. Tokens live in `frontend/src/styles/tokens.css`.

## Logo

- Files: `docs/design/ovagri-logo.png` (master), `frontend/public/logo.png` (served).
- Use on white or very light backgrounds. Never recolour, stretch, rotate or crop it; no shadow or outline.
- Minimum size: 40 px high in the app bar, 96 px on login / register screens.
- Clear space: at least the height of the leaf on every side.
- **To do:** ask the communication team for an SVG version and a square app icon (512×512, with padding)
  for the phone home screen.

## Colours

| Token | Hex | From the logo | Use |
|---|---|---|---|
| `--brand-green-700` | `#0A6B28` | Leaf base | **Primary**: main buttons, headings, active nav, focus border |
| `--brand-green-800` | `#075220` | — | Primary hover |
| `--brand-green-500` | `#3F9A1E` | Leaf middle | Illustrations, charts |
| `--brand-lime-400` | `#A8D800` | Leaf highlight, "GRI" | Decoration and gradients only — **never text** (contrast too low) |
| `--brand-orange-500` | `#F89000` | Arc, "OVA" | **Accent**: highlights, "to pay" states, secondary CTA (dark text on it) |
| `--brand-orange-600` | `#E87000` | Arc shade | Gradients |
| `--brand-orange-800` | `#A14D00` | — | Orange text on white (AA) |
| `--brand-grey-700` | `#4A4A4A` | "GROUPE" | Secondary text |

Brand gradient (orange → lime → green, like the logo arc and leaf): `--gradient-brand`. Used as the thin
line under the app bar; keep it as an accent, not a background for text.

Status colours: success = green, error = red `#B42318`, "to pay" = orange. Never rely on colour alone: always
pair it with a word or an icon.

## Typography

- Headings: **Poppins** 600/700 (rounded and friendly like the logo lettering).
- Body and forms: **Inter** 400/500/600.
- Base size 16 px; never below 14 px. The scanner screen uses 24–32 px for the employee's name.

## Layout and components

- Mobile-first. Employee flow: open app → see this week's days → **Reserve** in one tap.
- Rounded shapes echo the logo: cards 14 px radius, buttons fully rounded (pill).
- Tap targets ≥ 48 px. Visible focus ring in orange.
- Phones: navigation at the bottom (thumb reach). Desktop: navigation in the top bar.
- Light and dark themes are both defined in the tokens.
- RTL-ready: logical CSS properties only (Arabic will be added later).

## Tone

French by default, English available. Short, friendly sentences ("Réservez avant minuit la veille").
Use "vous". Error messages say what happened and what to do next.
