import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Garimpo',
  tagline: 'Catalog scraper, REST API and conversational search for a Brazilian sports store',
  favicon: 'img/favicon.svg',

  future: {
    v4: true,
  },

  url: 'https://ettorecsenatore.github.io',
  baseUrl: '/garimpo/',
  organizationName: 'EttoreCSenatore',
  projectName: 'garimpo',

  onBrokenLinks: 'throw',

  markdown: {
    mermaid: true,
  },
  themes: ['@docusaurus/theme-mermaid'],

  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'pt-BR'],
    localeConfigs: {
      en: {label: 'English', htmlLang: 'en'},
      'pt-BR': {label: 'Português (Brasil)', htmlLang: 'pt-BR'},
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/', // docs-only site
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/EttoreCSenatore/garimpo/tree/main/website/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Garimpo',
      logo: {
        alt: 'Garimpo',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docs',
          position: 'left',
          label: 'Documentation',
        },
        {
          type: 'localeDropdown',
          position: 'right',
        },
        {
          href: 'https://github.com/EttoreCSenatore/garimpo',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Project',
          items: [
            {label: 'GitHub', href: 'https://github.com/EttoreCSenatore/garimpo'},
            {label: 'Security policy', href: 'https://github.com/EttoreCSenatore/garimpo/blob/main/SECURITY.md'},
          ],
        },
      ],
      copyright: `Garimpo · MIT License · ${new Date().getFullYear()}`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'json', 'docker', 'yaml'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
