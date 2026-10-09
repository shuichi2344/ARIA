import type { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: 'https://aria-fyp.vercel.app',
      changeFrequency: 'weekly',
    },
  ]
}
