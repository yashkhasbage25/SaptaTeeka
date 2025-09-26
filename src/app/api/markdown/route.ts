// src/app/api/markdown/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { config } from '@/app/config';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const page = searchParams.get('page') || 'kavacham';
  
  try {
    let content: string;
    
    if (config.localDev) {
      // Read from local filesystem
      const filePath = path.join(process.cwd(), `src/app/content/${page}.md`);
      content = await fs.readFile(filePath, 'utf8');
    } else {
      // Fetch from GitHub
      const url = `${config.githubRepoUrl}/src/app/content/${page}.md`;
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch from GitHub: ${response.statusText}`);
      }
      
      content = await response.text();
    }
    
    return NextResponse.json({ content });
  } catch (error) {
    console.error(`Error loading markdown for ${page}:`, error);
    return NextResponse.json(
      { error: `Failed to load content for ${page}` },
      { status: 500 }
    );
  }
}
