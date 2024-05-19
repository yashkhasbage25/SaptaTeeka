base_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>सप्तशतीसप्तटीका</title>
    <meta charset="utf-8">
    <!-- Meta -->
    <meta name="keywords" content="Saptashati SaptaTeeka" />
    <meta name="author" content="Yash Khasbage">
    <meta name="robots" content="" />
    <meta name="description" content="Several Teekas of Saptashati">

    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="shortcut icon" type="image/png" href="images/favicon.png">
    <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="css/main.css" type="text/css" />
    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script rel="text/javascript" src="js/main.js" ></script>
</head>
<body>

<!-- Navbar -->
<div class="d-flex align-items-center justify-content-between p-3">
  <button id="toggleNav" class="btn btn-dark">&#9776;</button>
</div>
<nav class="navbar">
  <div class="p-3">
    <h2>
      <a href="/{repo_name}/index.html" class="nav-link">सप्तशती
       सप्तटीका
      </a>
    </h2>
    <ul class="गुप्तवतीप्रदीपौ।">
      <div class="nav-item"><a class="nav-link" href="/{repo_name}/index.html">मुखम्</a></div>
      <div class="nav-item"><a class="nav-link" href="/{repo_name}/kavacham.html">कवचम्</a></div>
      <div class="nav-item"><a class="nav-link" href="/{repo_name}/argala.html">अर्गला</a></div>
      <div class="nav-item"><a class="nav-link" href="#">कीलकम्</a></div>
      <!-- Add more links here -->
    </ul>
  </div>
</nav>

<!-- Content -->
<div class="content">
  {content}
</div>

<!-- Bootstrap JS and jQuery -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js" 
  integrity="sha512-v2CJ7UaYy4JwqLDIrZUI/4hqeoQieOmAZNXBeQyjo21dadnwR+8ZaIJVT8EE2iyI61OV8e6M8PP2/4hpQINQ/g==" 
  crossorigin="anonymous" referrerpolicy="no-referrer"></script>

<script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.5.4/dist/umd/popper.min.js"></script>
<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
</body>
</html>
"""


import re
from bs4 import BeautifulSoup   

roman2dev = {
    "guptavati": "गुप्तवती",
    "pradeepa": "प्रदीप",
    "moolam": "मूलम्",
}
repo_name = "docs"
index_content = """
<center>
॥ श्रीसिद्धिबुद्धिसहितश्रीमद्गणाधिपतये नमः ॥
<br>
Sharing an important book that went out of # printing - Saptashati-SaptaTeeka.
<br>
<img src="images/stuyate-sa-na-kim-janaih.png" >
</center>
"""

index_html = base_html.format(content=index_content, repo_name=repo_name)

def format_html(html_string):
    soup = BeautifulSoup(html_string, 'html.parser')
    formatted_html = soup.prettify()
    return formatted_html

def format_shloka(shloka):
    """
    Formats a shloka to be displayed on a webpage
    """
    lines = shloka.split('\n')
    formatted = '<div class="shloka">'
    for line in lines:
        space_danda = r'(?<!\s)।(?!\s)'
        space_double_danda = r'(?<!\s)॥(?!\s)'
        line = re.sub(space_danda, ' ।', line)
        line = re.sub(space_double_danda, ' ॥', line)
        formatted += f'<p>{line}</p>'
    formatted += '</div>'
    return formatted

def chapter_to_html(chapter):
    """
    Converts a chapter to an HTML string
    """
    innerhtml = '<div class="container">'
    for child in chapter:
        if child.tag == 'head':
            innerhtml += f'<p class="h2" style="padding-top: 20px;">{child[0].text}</p>'
        elif child.tag == 'body':
            for subbody in child:
                if subbody.tag == 'uvacha':
                    innerhtml += '<div class="uvacha">'
                    innerhtml += f'<p>{subbody.text}</p>'
                    innerhtml += '</div>'
                    # print("found uvacha", subbody.text)
                elif subbody.tag == 'moolam':
                    innerhtml += '<div class="shloka">'
                    innerhtml += f'<p class="h5 teeka-name">{roman2dev[subbody.tag]}</p>'
                    innerhtml += format_shloka(subbody.text)
                    innerhtml += '</div>'
                    # print("found moolam", subbody.text)
                elif subbody.tag == 'teeka':
                    # import pdb; pdb.set_trace()
                    teeka_name = subbody.get('name')
                    # import pdb; pdb.set_trace()
                    # print("entering teeka", teeka_name)
                    if teeka_name not in roman2dev:
                        raise ValueError(f"check this subbody: {subbody.text}")
                    
                        # print("teeka text", subbody.text)
                    teeka_text = ""
                    for subsubbody in subbody:
                        if subsubbody.tag == 'ignore':
                            # print("ignoring", subsubbody.text)
                            pass
                        elif subsubbody.tag == 'verse':
                            teeka_text += format_shloka(subsubbody.text)
                            # print("verse", subsubbody.text)
                        elif subsubbody.tag == 'prose':
                            # print("entering prose", subsubbody.text)
                            for subprose in subsubbody:
                                if subprose.tag == 'quote':
                                    teeka_text += f'<i>{subprose.text}</i>'
                                    # print("quote", subsubbody.text)
                                elif subprose.tag == 'prose':
                                    teeka_text += subprose.text
                                    # print("prose", subprose.text)
                                elif subprose.tag == 'vyakarana':
                                    teeka_text += f'<a href="{subprose.get("link")}"><span title="Vyakarana">{subprose.text}</span></a>'
                                    # print("vyakarana", subprose.text)
                                elif subprose.tag == 'unclear# print':
                                    teeka_text += f'<span title="This text is unclear">{subprose.text}</span>'
                                    # print("unclear", subprose.text)
                                elif subprose.tag == 'a':
                                    if subprose.get('href') is not None:
                                        teeka_text += f'<a href="{subprose.get("href")}">{subprose.text}</a>'
                                        # print("a", subprose.text)
                                    else:
                                        teeka_text += f'{subprose.text}'
                                elif subprose.tag == 'unknown':
                                    teeka_text += f'<i>{subprose.text}</i>'
                                    # print("unknown", subprose.text)
                                elif subprose.tag == 'doubtful':
                                    teeka_text += f'<span title="{subprose.get("comment")}">{subprose.text}</span>'
                                    # print("doubtful", subprose.text)
                                elif subprose.tag == 'comment':
                                    teeka_text += f'<span title="{subprose.get("comment")}">?</span>'
                                    # print("comment", subprose.text)
                                elif subprose.tag == 'shruti':
                                    teeka_text += f'<i>{subprose.text}</i>'
                                    # print("shruti", subprose.text)
                                else:
                                    import pdb; pdb.set_trace()
                        elif subsubbody.tail:
                            # print("subsubboday tail", subsubbody.tail)
                            teeka_text += subsubbody.tail
                        else:
                            import pdb; pdb.set_trace()
                    if subbody.tail:
                        # print("subbodytail", subbody.tail)
                        teeka_text += subbody.tail
                    if len(teeka_text.strip()) > 0:
                        innerhtml += '<div class="teeka">'
                        innerhtml += f'<p class="h5 teeka-name">{roman2dev[teeka_name]}</p>'
                        innerhtml += teeka_text
                        innerhtml += '</div>'
                    # print("exiting teeka", teeka_name)
                else:
                    import pdb; pdb.set_trace()

    innerhtml += '</div>'
    # html = base_html.format(content=html, repo_name=repo_name)
    html = base_html.format(content=innerhtml, repo_name=repo_name)
    html = format_html(html)
    return html