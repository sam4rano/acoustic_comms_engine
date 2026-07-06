import { getRequestConfig } from "next-intl/server";
import { hasLocale } from "next-intl";

export const locales = ["en", "yo"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";

export function getLocaleFromRequest(headers: Headers): Locale {
  const accept = headers.get("accept-language") ?? "en";
  const tag = accept.split(",")[0]?.split("-")[0] ?? "en";
  if (locales.includes(tag as Locale)) return tag as Locale;
  return defaultLocale;
}

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(locales, requested) ? requested : defaultLocale;
  return { locale, messages: (await import(`@/messages/${locale}.json`)).default };
});
