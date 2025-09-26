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
        display: 'अर्गला'
    },
    {
        route: 'keelakam',
        display: 'कीलकम्'
    },
    {
        route: 'adhyaya1',
        display: 'प्रथमोऽध्यायः'
    }, 
    {
        route: 'adhyaya2',
        display: 'द्वितीयोऽध्यायः'
    },
    {
        route: 'adhyaya3',
        display: 'तृतीयोऽध्यायः'
    },
    {
        route: 'adhyaya4',
        display: 'चतुर्थोऽध्यायः'
    },
    {
        route: 'adhyaya5',
        display: 'पञ्चमोऽध्यायः'
    },
    {
        route: 'adhyaya6',
        display: 'षष्ठोऽध्यायः'
    },
    {
        route: 'adhyaya7',
        display: 'सप्तमोऽध्यायः'
    },
    {
        route: 'adhyaya8',
        display: 'अष्टमोऽध्यायः'
    },
    {
        route: 'adhyaya9',
        display: 'नवमोऽध्यायः'
    },
    {
        route: 'adhyaya10',
        display: 'दशमोऽध्यायः'
    },
    {
        route: 'adhyaya11',
        display: 'एकादशोऽध्यायः'
    },
    {
        route: 'adhyaya12',
        display: 'द्वादशोऽध्यायः'
    },
    {
        route: 'adhyaya13',
        display: 'त्रयोदशोऽध्यायः'
    },
    {
        route: 'pradhanika',
        display: 'प्राधानिकरहस्यम्'
    },
    {
        route: 'vaikrutika',
        display: 'वैकृतिकरहस्यम्'
    },
    {
        route: 'moorti',
        display: 'मूर्तिरहस्यम्'
    }
];

export { pageList };
export type { Page };