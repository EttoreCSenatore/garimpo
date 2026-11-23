import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docs: [
    'intro',
    'getting-started',
    {
      type: 'category',
      label: 'System',
      collapsed: false,
      items: ['how-it-works', 'architecture', 'api', 'chat-search', 'configuration'],
    },
    {
      type: 'category',
      label: 'Operations',
      items: ['deployment', 'backup-restore', 'monitoring', 'upgrade', 'security', 'responsible-use'],
    },
    {
      type: 'category',
      label: 'Project',
      items: ['vision', 'data-model', 'glossary', 'decisions', 'versioning', 'development', 'roadmap'],
    },
  ],
};

export default sidebars;
