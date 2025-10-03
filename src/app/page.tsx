'use client';

import Image from "next/image";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import { pageList, Page } from "./constants";
import React, { Component } from "react";
import ReactMarkdown from 'react-markdown';
import { Typography } from "@mui/material";
import remarkGfm from 'remark-gfm';
import 'github-markdown-css/github-markdown.css';
import './markdown-override.css';
import { Eczar } from "next/font/google";
import { config } from './config';

const eczar = Eczar({
  variable: "--font-eczar",
  weight: ["400", "500"],
  subsets: ["latin"],
});

interface HomeProps {
  initialMarkdownContent?: string;
  initialPage?: string;
};

interface HomeState {
  selectedPage: string;
  markdownContent: string;
  isLoading: boolean;
  error: string | null;
}

interface MarkdownRendererProps {
  content: string;
}

// Simple component to render markdown content
const MarkdownRenderer = ({ content }: MarkdownRendererProps) => (
  <ReactMarkdown remarkPlugins={[remarkGfm]}>
    {content}
  </ReactMarkdown>
);

export default class Home extends React.Component<HomeProps, HomeState> {
  constructor(props: HomeProps) {
    super(props);
    this.state = {
      selectedPage: props.initialPage || 'adhyaya1',
      markdownContent: props.initialMarkdownContent || '',
      isLoading: false,
      error: null
    };
  }

  componentDidMount() {
    // If no initial content was provided, fetch it
    if (!this.props.initialMarkdownContent) {
      this.fetchMarkdown(this.state.selectedPage);
    }
    
    // Log the current source mode
    console.log(`Content source: ${config.localDev ? 'Local Filesystem' : 'GitHub Repository'}`);
  }

  handlePageChange = (pageRoute: string) => {
    this.setState({ selectedPage: pageRoute });
    this.fetchMarkdown(pageRoute);
  };

  // Data Fetching Logic - now using an API route
  fetchMarkdown = async (pageRoute: string) => {
    this.setState({ isLoading: true, error: null });
    
    try {
      // Call our API route that will access the content based on config
      const response = await fetch(`/api/markdown?page=${pageRoute}`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch ${pageRoute}: ${response.statusText}`);
      }

      const data = await response.json();
      this.setState({ 
        markdownContent: data.content, 
        isLoading: false 
      });

    } catch (err: any) {
      console.error(err);
      this.setState({ 
        error: `Could not load content for "${pageRoute}". Check the URL and server.`, 
        isLoading: false 
      });
    }
  };

  render() {
    const { selectedPage, markdownContent, isLoading, error } = this.state;
    
    return (
      <div className="flex flex-row h-full text-lg text-white bg-fixed bg-cover bg-center bg-blend-multiply bg-[#c40c0c] bg-[linear-gradient(rgba(196,12,12,0.5),rgba(196,12,12,0.5))]">
        <Stack className="bg-[#ff6500] flex flex-col items-center justify-center w-60 flex-shrink-0 sticky top-0 h-screen">
          {pageList.map((page: Page) => (
            <Button 
              key={page.route} 
              onClick={() => this.handlePageChange(page.route)}
              variant={selectedPage === page.route ? 'contained' : 'text'}
              style={{ 
                color: 'white', 
                backgroundColor: selectedPage === page.route ? '#c40c0c' : 'transparent' 
              }}
            >
              <div className="text-white text-xl">
                {page.display}
              </div>
            </Button>
          ))}
          <div className="mt-4 text-xs opacity-70">
            Source: {config.localDev ? 'Local Files' : 'GitHub'}
          </div>
        </Stack>
        <Stack>
          <div className="p-24 overflow-y-auto">
            <div className={`w-3/5 markdown-body ${eczar.className}`}>
              {isLoading ? (
                <div>Loading content...</div>
              ) : error ? (
                <div className="text-yellow-300">Error: {error}</div>
              ) : (
                <MarkdownRenderer content={markdownContent} />
              )}
            </div>
          </div>
        </Stack>
      </div>
    );
  }
}
