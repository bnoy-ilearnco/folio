// Bundled, unmodified open font families. Sources and licenses accompany the files.
export const FONT_COLLECTION = [
  {
    "family": "Cardo",
    "group": "Publishing · Hebrew & English",
    "files": [
      {
        "path": "/fonts/collection/cardo/Cardo-Regular.ttf",
        "weight": "400",
        "style": "normal"
      },
      {
        "path": "/fonts/collection/cardo/Cardo-Bold.ttf",
        "weight": "700",
        "style": "normal"
      },
      {
        "path": "/fonts/collection/cardo/Cardo-Italic.ttf",
        "weight": "400",
        "style": "italic"
      }
    ],
    "note": ""
  },
  {
    "family": "Frank Ruhl Libre",
    "group": "Publishing · Hebrew & English",
    "files": [
      {
        "path": "/fonts/collection/frankruhllibre/FrankRuhlLibre[wght].ttf",
        "weight": "300 900",
        "style": "normal"
      }
    ],
    "note": ""
  },
  {
    "family": "Bellefair",
    "group": "Publishing · Hebrew & English",
    "files": [
      {
        "path": "/fonts/collection/bellefair/Bellefair-Regular.ttf",
        "weight": "400",
        "style": "normal"
      }
    ],
    "note": ""
  },
  {
    "family": "Libre Baskerville",
    "group": "Publishing · English",
    "files": [
      {
        "path": "/fonts/collection/librebaskerville/LibreBaskerville[wght].ttf",
        "weight": "400 700",
        "style": "normal"
      },
      {
        "path": "/fonts/collection/librebaskerville/LibreBaskerville-Italic[wght].ttf",
        "weight": "400 700",
        "style": "italic"
      }
    ],
    "note": ""
  },
  {
    "family": "Gveret Levin",
    "group": "Handwriting · Hebrew & English",
    "files": [
      {
        "path": "/fonts/collection/gveretlevin/GveretLevin-Regular.ttf",
        "weight": "400",
        "style": "normal"
      }
    ],
    "note": ""
  },
  {
    "family": "Playpen Sans Hebrew",
    "group": "Handwriting · Hebrew & English",
    "files": [
      {
        "path": "/fonts/collection/playpensanshebrew/PlaypenSansHebrew[wght].ttf",
        "weight": "100 800",
        "style": "normal"
      }
    ],
    "note": ""
  },
  {
    "family": "Solitreo",
    "group": "Handwriting · Hebrew & English",
    "files": [
      {
        "path": "/fonts/collection/solitreo/Solitreo-Regular.ttf",
        "weight": "400",
        "style": "normal"
      }
    ],
    "note": "Best for unpointed Hebrew; some vowel marks use fallback."
  },
  {
    "family": "Patrick Hand",
    "group": "Handwriting · English",
    "files": [
      {
        "path": "/fonts/collection/patrickhand/PatrickHand-Regular.ttf",
        "weight": "400",
        "style": "normal"
      }
    ],
    "note": ""
  },
  {
    "family": "Keter Aram Tsova",
    "group": "Scroll & manuscript · Hebrew",
    "files": [
      {
        "path": "/fonts/collection/keteraramtsova/KeterAramTsova.ttf",
        "weight": "400",
        "style": "normal"
      }
    ],
    "note": "Aleppo Codex style; includes vowels and cantillation."
  },
  {
    "family": "Stam Ashkenaz CLM",
    "group": "Scroll & manuscript · Hebrew",
    "files": [
      {
        "path": "/fonts/collection/stamashkenaz/StamAshkenazCLM.ttf",
        "weight": "400",
        "style": "normal"
      }
    ],
    "note": "Torah scroll lettering; best for unpointed Hebrew."
  },
  {
    "family": "Stam Sefarad CLM",
    "group": "Scroll & manuscript · Hebrew",
    "files": [
      {
        "path": "/fonts/collection/stamsefarad/StamSefaradCLM.ttf",
        "weight": "400",
        "style": "normal"
      }
    ],
    "note": "Torah scroll lettering; best for unpointed Hebrew."
  },
  {
    "family": "Uncial Antiqua",
    "group": "Scroll & manuscript · English",
    "files": [
      {
        "path": "/fonts/collection/uncialantiqua/UncialAntiqua-Regular.ttf",
        "weight": "400",
        "style": "normal"
      }
    ],
    "note": "Uncial manuscript display lettering."
  },
  {
    "family": "IM FELL English",
    "group": "Scroll & manuscript · English",
    "files": [
      {
        "path": "/fonts/collection/imfellenglish/IMFeENrm28P.ttf",
        "weight": "400",
        "style": "normal"
      },
      {
        "path": "/fonts/collection/imfellenglish/IMFeENit28P.ttf",
        "weight": "400",
        "style": "italic"
      }
    ],
    "note": "Historical printing face."
  }
] as const;
export const FONT_GROUPS = [...new Set(FONT_COLLECTION.map(font=>font.group))];
