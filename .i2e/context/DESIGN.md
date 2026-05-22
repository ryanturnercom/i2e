---
version: "alpha"
name: "AI Apprenticeship Community Design System"
description: "A pragmatic, master-craftsman aesthetic for a membership learning community. Monochrome charcoal-and-paper palette, soft elevated cards, calm reading rhythm, and quietly assertive uppercase action buttons. Designed for focus, long-form reading, and confident administrative workflows on community.ryanturner.com."
colors:
  primary: "#272727"
  primary-hover: "#3a3a3a"
  primary-foreground: "#ffffff"
  secondary: "#efefef"
  secondary-foreground: "#333333"
  tertiary: "#e8e0ff"
  tertiary-foreground: "#333333"
  neutral-50: "#fafafa"
  neutral-100: "#f9f9f9"
  neutral-200: "#f7f7f7"
  neutral-300: "#f5f5f5"
  neutral-400: "#f0f0f0"
  neutral-500: "#e5e5e5"
  neutral-600: "#e0e0e0"
  neutral-700: "#d4d4d4"
  neutral-800: "#d1d5db"
  neutral-900: "#cccccc"
  surface-background: "#efefef"
  surface-card: "#ffffff"
  surface-subtle: "#f5f5f5"
  surface-accent: "#f7f7f7"
  surface-hover: "#fafafa"
  surface-inset: "#f9f9f9"
  surface-muted: "#f0f0f0"
  surface-sidebar: "#272727"
  border-default: "#e0e0e0"
  border-subtle: "#e5e5e5"
  border-input: "#d1d5db"
  text-heading: "#333333"
  text-body: "#5f5f5f"
  text-muted: "#999999"
  text-disabled: "#cccccc"
  text-on-dark: "#ffffff"
  error: "#ef4444"
  error-foreground: "#ffffff"
typography:
  font-family-sans: "Poppins, ui-sans-serif, system-ui, sans-serif"
  weight-light: 300
  weight-regular: 400
  weight-medium: 500
  weight-semibold: 600
  weight-bold: 700
  line-height-tight: 1.2
  line-height-snug: 1.4
  line-height-normal: 1.7
  tracking-tight: "0px"
  tracking-wide: "1px"
  tracking-widest: "2px"
  display-lg:
    size: "32px"
    line-height: 1.2
    weight: 700
    letter-spacing: "0px"
  display-md:
    size: "24px"
    line-height: 1.3
    weight: 700
    letter-spacing: "0px"
  heading-lg:
    size: "20px"
    line-height: 1.4
    weight: 600
    letter-spacing: "0px"
  heading-md:
    size: "16px"
    line-height: 1.4
    weight: 600
    letter-spacing: "0px"
  body-md:
    size: "14px"
    line-height: 1.7
    weight: 400
    letter-spacing: "0px"
  body-sm:
    size: "13px"
    line-height: 1.5
    weight: 400
    letter-spacing: "0px"
  label-sm:
    size: "11px"
    line-height: 1.2
    weight: 600
    letter-spacing: "1px"
  label-xs:
    size: "10px"
    line-height: 1.2
    weight: 600
    letter-spacing: "1px"
  nav-label:
    size: "12px"
    line-height: 1.2
    weight: 600
    letter-spacing: "2px"
rounded:
  none: "0px"
  sm: "4px"
  default: "6px"
  md: "6px"
  lg: "8px"
  pill: "9999px"
  full: "9999px"
spacing:
  none: "0px"
  xxs: "2px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  xxl: "24px"
  xxxl: "30px"
  gutter: "30px"
  sidebar-width: "300px"
  content-max-width: "940px"
  page-padding: "30px"
  breakpoint-mobile: "1024px"
components:
  button-primary:
    background: "{colors.primary}"
    color: "{colors.primary-foreground}"
    border: "0px"
    border-radius: "{rounded.default}"
    padding: "15px 20px 12px 20px"
    font-family: "{typography.font-family-sans}"
    font-size: "11px"
    font-weight: "{typography.weight-semibold}"
    letter-spacing: "1px"
    text-transform: "uppercase"
  button-primary-hover:
    background: "{colors.primary-hover}"
    color: "{colors.primary-foreground}"
  button-primary-focus:
    background: "{colors.primary}"
    color: "{colors.primary-foreground}"
    outline: "2px solid {colors.primary}"
    outline-offset: "2px"
  button-primary-disabled:
    background: "{colors.primary}"
    color: "{colors.primary-foreground}"
    opacity: 0.5
  button-outline:
    background: "transparent"
    color: "{colors.primary}"
    border: "1px solid {colors.primary}"
    border-radius: "{rounded.default}"
    padding: "15px 20px 12px 20px"
    font-size: "11px"
    font-weight: "{typography.weight-semibold}"
    letter-spacing: "1px"
    text-transform: "uppercase"
  button-outline-hover:
    background: "{colors.primary}"
    color: "{colors.primary-foreground}"
    border: "1px solid {colors.primary}"
  button-secondary:
    background: "{colors.secondary}"
    color: "{colors.text-heading}"
    border: "0px"
    border-radius: "{rounded.default}"
    padding: "15px 20px 12px 20px"
    font-size: "11px"
    font-weight: "{typography.weight-semibold}"
    letter-spacing: "1px"
    text-transform: "uppercase"
  button-secondary-hover:
    background: "{colors.border-default}"
    color: "{colors.text-heading}"
  button-sm:
    padding: "10px 16px 8px 16px"
    font-size: "10px"
    border-radius: "{rounded.default}"
  button-lg:
    padding: "18px 28px 15px 28px"
    font-size: "11px"
    border-radius: "{rounded.default}"
  input-text:
    background: "{colors.surface-card}"
    color: "{colors.text-body}"
    border: "1px solid {colors.border-default}"
    border-radius: "{rounded.default}"
    padding: "8px 12px 8px 12px"
    font-family: "{typography.font-family-sans}"
    font-size: "14px"
    placeholder-color: "{colors.text-muted}"
  input-text-focus:
    background: "{colors.surface-card}"
    color: "{colors.text-body}"
    border: "1px solid {colors.primary}"
    outline: "2px solid {colors.primary}"
    outline-offset: "0px"
  input-text-disabled:
    background: "{colors.surface-subtle}"
    color: "{colors.text-disabled}"
    border: "1px solid {colors.border-default}"
    opacity: 0.5
  input-auth:
    background: "{colors.surface-card}"
    color: "{colors.text-body}"
    border: "1px solid {colors.border-input}"
    border-radius: "{rounded.default}"
    padding: "8px 12px 8px 12px"
    font-size: "14px"
  card:
    background: "{colors.surface-card}"
    color: "{colors.text-body}"
    border: "0px"
    border-radius: "{rounded.default}"
    padding: "30px"
    box-shadow: "0px 2px 40px rgba(0,0,0,0.07)"
  card-header:
    background: "{colors.surface-card}"
    padding: "30px 30px 0px 30px"
    color: "{colors.text-heading}"
  card-content:
    padding: "30px"
    color: "{colors.text-body}"
  card-footer:
    padding: "0px 30px 30px 30px"
    color: "{colors.text-body}"
  badge-default:
    background: "{colors.primary}"
    color: "{colors.primary-foreground}"
    border-radius: "{rounded.pill}"
    padding: "2px 8px 2px 8px"
    font-size: "10px"
    font-weight: "{typography.weight-semibold}"
    letter-spacing: "0px"
    text-transform: "none"
  badge-destructive:
    background: "{colors.error}"
    color: "{colors.error-foreground}"
    border-radius: "{rounded.pill}"
    padding: "2px 8px 2px 8px"
    font-size: "10px"
    font-weight: "{typography.weight-semibold}"
  sidebar:
    background: "{colors.surface-sidebar}"
    color: "{colors.text-on-dark}"
    width: "300px"
    padding: "30px"
    border-right: "0px"
  sidebar-nav-item:
    background: "transparent"
    color: "{colors.text-on-dark}"
    padding: "10px 12px 10px 12px"
    border-radius: "{rounded.default}"
    font-size: "12px"
    font-weight: "{typography.weight-semibold}"
    letter-spacing: "2px"
    text-transform: "uppercase"
  sidebar-nav-item-hover:
    background: "{colors.primary-hover}"
    color: "{colors.text-on-dark}"
  sidebar-nav-item-active:
    background: "{colors.primary-hover}"
    color: "{colors.text-on-dark}"
  page-container:
    background: "{colors.surface-background}"
    color: "{colors.text-body}"
    padding: "30px"
    max-width: "940px"
  switch-track-on:
    background: "{colors.primary}"
    border-radius: "{rounded.pill}"
  switch-track-off:
    background: "{colors.neutral-700}"
    border-radius: "{rounded.pill}"
  switch-thumb:
    background: "{colors.surface-card}"
    border-radius: "{rounded.full}"
  mention-pill:
    background: "{colors.tertiary}"
    color: "{colors.text-heading}"
    border-radius: "{rounded.default}"
    padding: "2px 6px 2px 6px"
    font-size: "14px"
    font-weight: "{typography.weight-medium}"
  divider:
    background: "{colors.border-default}"
    color: "{colors.border-default}"
    border: "0px"
  divider-subtle:
    background: "{colors.border-subtle}"
    color: "{colors.border-subtle}"
    border: "0px"
---

## Overview

The AI Apprenticeship Community interface dresses itself like a quiet, well-lit workshop rather than a hype-driven SaaS dashboard. It pairs a dark charcoal sidebar with a soft paper-grey canvas and white content cards, communicating focus, longevity, and craft. The system is designed for adult practitioners — operations directors, mid-career specialists, and advisors — who read long-form posts, work through structured 30-day curricula, and toggle between admin tools and member experiences without visual noise.

Density is moderate to relaxed: generous 30px gutters, a centered 940px reading column, and 14px body type set on a 24px leading line make sustained reading comfortable. Action surfaces stay restrained — uppercase 11px buttons, hairline borders, and a single dark accent — so emphasis is reserved for content. The aesthetic goal is "battle-tested, not buzzworthy": pragmatic, confident, and quietly authoritative.

## Colors

The palette is intentionally monochrome with one supporting tertiary lilac. There is no decorative brand hue — gravity comes from contrast and surface layering, not saturation.

- **Primary (`#272727` charcoal)** — Used for the fixed sidebar, primary buttons, badges, and dark accent surfaces. It is also the focus-ring color via `{colors.primary}` translucent. Apply when an action is the single most important choice on the screen.
- **Primary hover (`#3a3a3a`)** — Hover state for any dark surface (primary buttons, active sidebar nav items, dropdown triggers).
- **Secondary (`#efefef`)** — The page canvas. Also acts as the secondary button background on cards. Pairs with `text-heading` (`#333333`) for legibility.
- **Tertiary (`#e8e0ff` mention lilac)** — The only chromatic accent. Reserved for @mention highlights inside the markdown editor. Do not promote to other UI; its scarcity is what makes it work.
- **Neutral surface ladder (`#fafafa → #e0e0e0`)** — A five-step ladder of warm-greys for layered surfaces: `surface-hover` (row hover), `surface-inset` (recessed panels), `surface-accent` (info boxes), `surface-subtle` (inputs, code blocks), `surface-muted` (inline code, table headers).
- **Border (`#e0e0e0` default, `#e5e5e5` subtle, `#d1d5db` input)** — Hairlines that separate without shouting. `border-input` is reserved for auth/OAuth forms where the input must feel a touch firmer.
- **Text ladder** — `text-heading` (`#333333`) for headings, `text-body` (`#5f5f5f`) for body copy and icons, `text-muted` (`#999999`) for timestamps and metadata, `text-disabled` (`#cccccc`) for disabled states only.
- **Error (`#ef4444`)** — Destructive badges and inline error messaging only. Never used as a primary action color.

## Typography

The entire interface is set in **Poppins** (Google Fonts, weights 300–700), loaded via Next.js `next/font/google` and exposed as `--font-poppins`.

- **Display & headings** — Poppins 600/700 at 16–32px, color `text-heading` (`#333333`), tight to snug leading. Used for page titles, card titles, and feature sections.
- **Body** — Poppins 400 at 14px / 24px line-height, color `text-body` (`#5f5f5f`). This is the workshop's default voice: calm, readable, unhurried.
- **Labels & actions** — Poppins 600 at 10–11px **uppercase** with 1px letter-spacing. Buttons follow this rule strictly; the slightly heavier top padding (15px / 12px) optically centers uppercase glyphs.
- **Nav labels** — 12px uppercase Poppins 600 with **2px** letter-spacing (`.nav-item-text`). Reserved for sidebar nav and section dividers; this is the system's most decorated text style — use sparingly.
- **Captions / metadata** — 13px or 12px regular weight in `text-muted`. Used for timestamps, author bylines, and supporting captions.

Avoid mixing other typefaces. Highlighting code (rehype-highlight) and Lucide React icons should inherit body color unless a heading context overrides them.

## Layout

- **Macro structure** — A fixed **300px sidebar** on the left (`#272727`) plus a fluid main column. Main content is centered with a `max-w-[940px]` constraint and `30px` page padding on all sides.
- **Mobile** — Below the 1024px breakpoint the sidebar collapses into a hamburger overlay; main column drops the max-width and uses `16px–20px` padding.
- **Grid & rhythm** — Cards stack vertically with `30px` gutter spacing. Inside cards, 30px padding is the default for header/content/footer (CardHeader sets `p-[30px] pb-0`, CardContent `p-[30px]`, CardFooter `p-[30px] pt-0`). Lists and feeds use 1–2 rem vertical gaps; tables use `surface-hover` row hovers.
- **Spacing scale** — Use the token ladder (2/4/8/12/16/20/24/30) rather than free numbers. 30 is the dominant macro unit; 8 and 12 dominate micro spacing inside form controls.
- **Reading column** — Long-form content (posts, lessons, broadcasts) should never exceed 940px wide. Within those, prose should not exceed ~70 characters per line; rely on the centered container rather than per-block max-width hacks.

## Elevation & Depth

Depth is achieved through three mechanisms — never colored shadows or heavy borders.

1. **The signature card shadow** — `box-shadow: 0 2px 40px rgba(0,0,0,0.07)` (token `shadow-card`). It is a wide, soft, low-opacity drop. Apply it to all `Card` components and to floating panels (popovers, dropdowns). Do not stack multiple shadow rings.
2. **Surface stepping** — Slight value shifts (`#fafafa → #f9f9f9 → #f7f7f7 → #f5f5f5 → #f0f0f0`) signal depth in lieu of borders. Recessed panels use `surface-inset`; emphasized info boxes use `surface-accent`; row hovers use `surface-hover`.
3. **Border hairlines** — 1px borders in `border-default` are the primary divider mechanism. Use `border-subtle` when stacking inside an already-bordered card to avoid double-line patterns.

Dark surfaces (sidebar, primary buttons) carry no shadow; they own their depth through value contrast.

## Shapes

The shape language is **rectangular with softly rounded corners**. There are exactly three radius tokens in active use:

- **`rounded.sm` (4px)** — Reserved for very small inline elements (skill badges, code chips).
- **`rounded.default` (6px)** — The system default. Applies to buttons, inputs, cards, dropdowns, dialogs, and any rectangular container that needs to feel "finished but not pillowy."
- **`rounded.pill` (9999px)** — Reserved for badges, switch tracks, and avatar circles. Used to signal status or identity, never structure.

No card or container should exceed an 8px radius. The brand reads as workshop-pragmatic; oversized rounding feels consumer-app and is off-tone. Borders are hairline (`1px`) when present; many surfaces rely on shadow + value contrast and use no border at all.

## Components

- **Button (primary / outline / secondary)** — Uppercase 11px Poppins 600 with 1px tracking, asymmetric padding (`pt-[15px] pb-[12px]`) to optically center caps. Default is dark-on-light (`bg-sidebar-bg text-white`); outline inverts on hover; secondary uses page background. Sizes `sm` (10px, tighter padding) and `lg` (28px horizontal) are available.
- **Input** — White card-tone background, 1px `border-default` hairline, 6px radius. On focus, the border becomes `primary` and a 2px translucent primary ring (`primary @ 20% opacity`) appears. Placeholder text is body text at 50% opacity.
- **Card** — Pure white background, 6px radius, no border, signature wide soft shadow. Use `CardHeader → CardContent → CardFooter` for vertical 30px rhythm. Never combine the card shadow with a border on the same element.
- **Badge** — Fully pill (9999px), 10px semibold. Default uses primary charcoal on white text. Destructive variant uses `error` red. Avoid bespoke badge palettes.
- **Sidebar nav item** — Uppercase 12px Poppins 600 with 2px tracking, white-on-charcoal. Hover and active states share the `primary-hover` (`#3a3a3a`) background. No left-border accent rail — color shift alone signals state.
- **Switch** — Pill track. On = `primary`, Off = `switch-inactive` (`#d4d4d4`). White thumb.
- **Markdown mention pill** — Lilac (`tertiary`) background, heading-color text, 6px radius, regular body size. This is the single chromatic accent in the system; do not introduce its color elsewhere.
- **Data table** — Header row in `surface-hover` or `surface-muted`, hairline `border-subtle` between rows, row hover in `surface-hover`. Body cells use 14px body type.
- **Dialog / Dropdown (Radix)** — Inherits card styling: white background, 6px radius, card shadow. Headers and footers use the same 30px padding rhythm as Card.

## Do's and Don'ts

**Do**

- Use `text-body` (`#5f5f5f`) for default copy and `text-heading` (`#333333`) for any heading; rely on weight (600/700) and size for hierarchy.
- Reach for the surface ladder (`surface-subtle`, `surface-inset`, `surface-accent`, `surface-hover`, `surface-muted`) before adding a border to express depth.
- Keep all interactive labels uppercase with 1–2px letter-spacing — buttons, nav items, eyebrow labels. Consistency in this micro-rule is part of the brand's feel.
- Respect the 30px gutter and the 940px reading column; let whitespace do work that borders and shadows would otherwise do.
- Pair primary buttons with at most one secondary action per screen — restraint is the design.
- Verify keyboard focus: every interactive control inherits the `focus-visible:ring-2 ring-primary/20 ring-offset-2` pattern; do not strip it.

**Don't**

- Don't introduce additional brand hues, gradients, or saturated accents. The lilac mention pill is the only chromatic element and is reserved.
- Don't use colored shadows, heavy 4px+ shadows, or shadow stacks. The single `0 2px 40px rgba(0,0,0,0.07)` ring is sufficient.
- Don't combine the card shadow with a visible border on the same element — pick one.
- Don't promote `text-muted` (`#999999`) to primary body copy; its 2.85:1 contrast on white is for metadata and timestamps only.
- Don't use `text-disabled` (`#cccccc`) for any enabled control or readable text — it is for disabled state only and intentionally fails AA.
- Don't introduce typefaces other than Poppins, and don't ship sentence-case button labels — uppercase tracking is the system's voice for actions.
- Don't exceed a 6px radius on containers (8px max in rare cases like full-screen mobile sheets). Oversized rounding reads consumer-app and is off-brand.
- Don't use the destructive red as a primary action color — it is reserved for irreversible/error states only.
- Don't add per-component margin hacks; use the spacing scale (2/4/8/12/16/20/24/30) so vertical rhythm stays consistent across admin and member views.
