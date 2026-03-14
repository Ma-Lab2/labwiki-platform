import { computed } from 'vue'
import { useSettingsStore } from '../stores/settings'
import zhCN from '../locales/zh-CN'
import enUS from '../locales/en-US'

const messages = {
  'zh-CN': zhCN,
  'en-US': enUS,
} as const

type LocaleKey = keyof typeof messages

export function useLocale() {
  const settings = useSettingsStore()

  const t = computed(() => messages[(settings.locale as LocaleKey) || 'zh-CN'])

  function setLocale(locale: LocaleKey) {
    settings.locale = locale
  }

  return { t, setLocale }
}
