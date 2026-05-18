import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import starlight from '@astrojs/starlight';

const site = process.env.UMMAYA_DOCS_SITE ?? 'https://ummaya.dev';
const base = process.env.UMMAYA_DOCS_BASE;

export default defineConfig({
  site,
  ...(base ? { base } : {}),
  integrations: [
    sitemap(),
    starlight({
      title: 'UMMAYA Docs',
      description:
        'User, operator, and agent-readable documentation for the UMMAYA national AX harness.',
      defaultLocale: 'en',
      locales: {
        en: { label: 'English' },
        ko: { label: '한국어' },
        ch: { label: '中文', lang: 'zh-CN' },
        jg: { label: '日本語', lang: 'ja' },
      },
      logo: {
        src: './src/assets/ummaya-logo.png',
        alt: 'UMMAYA',
      },
      favicon: '/favicon.png',
      head: [
        {
          tag: 'link',
          attrs: {
            rel: 'icon',
            type: 'image/png',
            sizes: '64x64',
            href: '/favicon.png',
          },
        },
        {
          tag: 'link',
          attrs: {
            rel: 'icon',
            type: 'image/x-icon',
            href: '/favicon.ico',
          },
        },
        {
          tag: 'link',
          attrs: {
            rel: 'apple-touch-icon',
            sizes: '180x180',
            href: '/apple-touch-icon.png',
          },
        },
        {
          tag: 'link',
          attrs: {
            rel: 'manifest',
            href: '/site.webmanifest',
          },
        },
      ],
      customCss: ['./src/styles/custom.css'],
      components: {
        ThemeProvider: './src/components/DarkThemeProvider.astro',
        ThemeSelect: './src/components/NoThemeSelect.astro',
      },
      editLink: {
        baseUrl: 'https://github.com/umyunsang/UMMAYA/edit/main/docs-site/',
      },
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/umyunsang/UMMAYA',
        },
      ],
      sidebar: [
        {
          label: 'Start',
          translations: {
            ko: '시작',
            'zh-CN': '开始',
            ja: 'はじめに',
          },
          items: [
            { slug: 'start/why-ummaya' },
            { slug: 'start/what-ummaya-can-do-today' },
            { slug: 'start/quickstart' },
            { slug: 'start/first-successful-session' },
            { slug: 'start/what-you-can-ask' },
            { slug: 'start/what-happens-after-you-ask' },
          ],
        },
        {
          label: 'Trust And Safety',
          translations: {
            ko: '신뢰와 안전',
            'zh-CN': '信任与安全',
            ja: '信頼と安全',
          },
          items: [
            { slug: 'trust/live-mock-handoff' },
            { slug: 'trust/permissions-and-consent' },
            { slug: 'trust/data-credentials-local-sessions' },
            { slug: 'trust/what-ummaya-will-not-do' },
            { slug: 'trust/official-handoff' },
          ],
        },
        {
          label: 'Use UMMAYA',
          translations: {
            ko: '사용하기',
            'zh-CN': '使用 UMMAYA',
            ja: 'UMMAYA を使う',
          },
          items: [
            { slug: 'use/emergency-healthcare-weather-safety' },
            { slug: 'use/moving-housing-local-records' },
            { slug: 'use/welfare-household-support' },
            { slug: 'use/tax-fines-payments-utilities' },
            { slug: 'use/identity-certificates-mydata' },
            { slug: 'use/sessions-receipts-history' },
            { slug: 'use/troubleshooting' },
          ],
        },
        {
          label: 'Coverage',
          translations: {
            ko: '커버리지',
            'zh-CN': '覆盖范围',
            ja: 'カバレッジ',
          },
          items: [
            { slug: 'coverage/current-coverage' },
            { slug: 'coverage/live-adapters' },
            { slug: 'coverage/domain-roadmap' },
            { slug: 'coverage/adapter-matrix' },
            { slug: 'coverage/scenario-matrix' },
          ],
        },
        {
          label: 'Architecture',
          translations: {
            ko: '아키텍처',
            'zh-CN': '架构',
            ja: 'アーキテクチャ',
          },
          items: [
            { slug: 'architecture/harness-migration' },
            { slug: 'architecture/main-primitives' },
            { slug: 'architecture/agentic-rag-query-engine' },
          ],
        },
        {
          label: 'Build And Operate',
          translations: {
            ko: '구축과 운영',
            'zh-CN': '构建与运营',
            ja: '構築と運用',
          },
          items: [
            { slug: 'build/adapter-authoring' },
            { slug: 'build/llmops' },
          ],
        },
        {
          label: 'Reference',
          translations: {
            ko: '레퍼런스',
            'zh-CN': '参考',
            ja: 'リファレンス',
          },
          items: [
            { slug: 'reference/llm-readable-docs' },
          ],
        },
      ],
    }),
  ],
});
