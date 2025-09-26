// src/app/components/MarkdownLoader.tsx
import { promises as fs } from 'fs';
import path from 'path';
import { config } from '@/app/config';

export async function getMarkdownContent(pageRoute: string) {
  try {
    let content: string;
    
    if (config.localDev) {
      // Read from local filesystem
      const filePath = path.join(process.cwd(), `src/app/content/${pageRoute}.md`);
      content = await fs.readFile(filePath, 'utf8');
    } else {
      // Fetch from GitHub
      const url = `${config.githubRepoUrl}/src/app/content/${pageRoute}.md`;
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch from GitHub: ${response.statusText}`);
      }
      
      content = await response.text();
    }
    
    return content;
  } catch (error) {
    console.error(`Error loading markdown for ${pageRoute}:`, error);
    return `Failed to load content for ${pageRoute}.`;
  }
}
