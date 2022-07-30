from extractnet.name_crf import AuthorExtraction

extract = AuthorExtraction()

def test_baseline():
    examples = [
        ('By BASSEM MROUE, SARAH EL DEEB and ZEINA KARAM',  ['BASSEM MROUE', 'SARAH EL DEEB', 'ZEINA KARAM']),
        ('Bassem Mroue, Sarah El Deeb And Zeina Karam', ['Bassem Mroue', 'Sarah El Deeb', 'Zeina Karam'])
    ]
    for text, labels in examples:
        preds = extract(text)
        assert preds == labels

def test_author_extraction_other_case():

    examples = [
        ('蘇銘翰 圖片來源／Toyota', ['蘇銘翰']),
        ('Christophe Franken (avec Y. T.)', ['Christophe Franken']),
        ('Mohammad Arief Hidayat,Ahmad Farhan Faris',['Mohammad Arief Hidayat', 'Ahmad Farhan Faris']),
        ('Corentin Pennarguear, correspondant à New York',['Corentin Pennarguear']),
        ('Resya Kania, PhD Candidate in Social Policy,), University of Birmingham', ['Resya Kania']),
        ('Galen Emanuele | Shift Yes', ['Galen Emanuele']),
        ('撰文／莊正賢', ['莊正賢']),
        ('鉅亨網編輯江泰傑',['江泰傑']),
        ('（林媛玲／台北報導）',['林媛玲']),
        ('聯合報 / 記者潘乃欣／台北即時報導',  ['潘乃欣']),
        ('【財訊快報陳孟朔】',   ['陳孟朔']),
    ]
    for text, labels in examples:
        preds = extract(text)
        assert preds == labels
