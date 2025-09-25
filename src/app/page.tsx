'use client';

import Image from "next/image";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import { pageList, Page } from "./constants";
import React, { Component } from "react";
import ReactMarkdown from 'react-markdown';


interface HomeProps {};
interface HomeState {
  selectedPage: string;
}

interface MarkdownRendererProps {
  pageRoute: string;
}

interface MarkdownRendererState {
  markdownContent: string;
  isLoading: boolean;
  error: string | null;
}

class MarkdownRenderer extends Component<MarkdownRendererProps, MarkdownRendererState> {
  constructor(props: MarkdownRendererProps) {
    super(props);
    this.state = {
      markdownContent: '',
      isLoading: false,
      error: null,
    };
  }

  // Lifecycle method to fetch data when the component mounts or props change
  componentDidMount() {
    this.fetchMarkdown(this.props.pageRoute);
  }

  componentDidUpdate(prevProps: MarkdownRendererProps) {
    if (prevProps.pageRoute !== this.props.pageRoute) {
      this.fetchMarkdown(this.props.pageRoute);
    }
  }

  // Data Fetching Logic
  fetchMarkdown = async (pageRoute: string) => {
    this.setState({ isLoading: true, error: null, markdownContent: '' });
    const url = `https://raw.githubusercontent.com/yashkhasbage25/SaptaTeeka/refs/heads/main/src/app/content/${pageRoute}.md`; // Your dynamic URL

    try {
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch ${pageRoute}: ${response.statusText}`);
      }

      const text = await response.text();
      this.setState({ markdownContent: text, isLoading: false });

    } catch (err: any) {
      console.error(err);
      this.setState({ 
        error: `Could not load content for "${pageRoute}". Check the URL and server.`, 
        isLoading: false 
      });
    }
  };

  render() {
    const { markdownContent, isLoading, error } = this.state;

    if (isLoading) {
      return <div className="p-8">Loading content...</div>;
    }

    if (error) {
      return <div className="p-8 text-yellow-300">Error: {error}</div>;
    }

    // Use ReactMarkdown to safely render the fetched content
    return (
      <div className="prose prose-invert p-8 max-w-none"> 
        <ReactMarkdown>{markdownContent}</ReactMarkdown>
      </div>
    );
  }
}


export default class Home extends React.Component<HomeProps, HomeState> {
  constructor(props: HomeProps) {
    super(props);
    this.state = {
      selectedPage: 'home'
    };
  }

  render() {
    return (
      <div className="flex flex-row h-full text-lg text-white bg-fixed bg-cover bg-center bg-blend-multiply bg-[#c40c0c] bg-[linear-gradient(rgba(196,12,12,0.8),rgba(196,12,12,0.8)),url('https://yashkhasbage25.github.io/SaptaTeeka/images/15273928_5588454.jpg')]">
        <Stack spacing={1} className="bg-[#ff6500] flex flex-col items-center justify-center w-60">
          {pageList.map((page: Page) => (
            <Button key={page.route} onClick={() => this.setState({ selectedPage: page.route })}>
              {page.display}
            </Button>
          ))}
        </Stack>
        <Stack>
          {/* render markdown page from url http://placeholder.com/{selectedPage} */}
          <MarkdownRenderer pageRoute={this.state.selectedPage} />
        </Stack>
      </div>
    );
  }
}