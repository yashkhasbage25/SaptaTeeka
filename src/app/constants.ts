interface Page {
  route: string;
  display: string;
}

const pageList: Page[] = [
    {
        route: 'home',
        display: 'मुखम्'
    },
    {
        route: 'kavacham',
        display: 'कवचम्'
    },
    {
        route: 'argala',
        display: 'अर्जला'
    },
    {
        route: 'keelakam',
        display: 'किल्लकम्'
    },
    {
        route: 'chapter1',
        display: 'अध्याय1'
    }, 
    {
        route: 'chapter2',
        display: 'अध्याय2'
    }
];

export { pageList };
export type { Page };