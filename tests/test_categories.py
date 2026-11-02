#!/usr/bin/env python3
"""Category QA: fresh meat, alcohol, exceptions and browser/Python parity."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from categories import RULES,category_for,normalize_category_text

rules=json.loads((ROOT/"data/category_rules.json").read_text(encoding="utf-8"))["rules"]
labels=[rule["label"] for rule in rules]
assert len(rules)>=40
assert len(labels)==len(set(labels))
assert all(r.get("group") and r.get("pattern") for r in rules)
group={r["label"]:r["group"] for r in rules}
assert group["Свіжа птиця"]=="Свіже м’ясо та птиця"
assert group["Свіжа свинина"]=="Свіже м’ясо та птиця"
assert group["Ковбаси, сосиски та сардельки"]=="Ковбаси та м’ясні вироби"
assert group["Пиво"]==group["Вино"]=="Алкоголь і альтернативи"
cases={
    "Філе курчат-бройлерів Чебатурочка охолоджене":"Свіжа птиця",
    "Стегно куряче охолоджене Вл/Вир ваг":"Свіжа птиця",
    "Стейк свинний із корейки б/к охол.ваг":"Свіжа свинина",
    "Яловичина лопатка охолоджена":"Свіжа яловичина та телятина",
    "Фарш 0,5 кг Своя Лінія Домашній охолоджений":"Фарш і субпродукти",
    "Шашлик курячий охол.ваг":"М’ясні напівфабрикати та маринади",
    "Куряча гомілка в маринаді":"М’ясні напівфабрикати та маринади",
    "Ковбаски Домашні для запік.в.в,ох.ваг":"М’ясні напівфабрикати та маринади",
    "Ковбаса М'ясна історія Салямі Люкс":"Ковбаси, сосиски та сардельки",
    "Шинка Argal Делікатесна з індички":"Шинка, бекон та м’ясні делікатеси",
    "Слойка з індичкою та сиром фета":"Булочки, круасани та випічка",
    "Салат Олів'є з куркою":"Готові страви та салати",
    "Картопляні зрази з м'ясом":"Готові страви та салати",
    "Корм для котів з куркою":"Корми та товари для тварин",
    "Пресерви Оселедець філе-шматочки зі спеціями":"Рибні консерви та пресерви",
    "Вино Pascal Bouchard Chablis Le Classique":"Вино",
    "Вино Perles Noires Malb.ч/сух13,5%":"Вино",
    "Вино ігр.0,75л 8,4% Charles du Lac Brut":"Ігристі вина та шампанське",
    "Вино б/а Augustin Sans р/нсух0,0%":"Безалкогольне пиво та вино",
    "Пиво св.Kaiserdom Pilsner 4,7%":"Пиво",
    "Пивo 1,1л Obolon Premium Extra Brew":"Пиво",
    "Пиво безалкогольне 0,0%":"Безалкогольне пиво та вино",
    "Горілка 0,5л Хлібний Дар Класична 40%":"Горілка",
    "Віскі шотландський":"Віскі та бурбон",
    "Коньяк український 3 зірки":"Коньяк та бренді",
    "Ром Captain Morgan":"Ром",
    "Джин Gordon's London Dry":"Джин",
    "Текіла Blanco":"Текіла",
    "Бальзам 0,5л Таїна Знахарки 40%":"Лікери, вермути та настоянки",
    "Шоколад Ritter Sport з ямайським ромом":"Шоколад та шоколадні батончики",
    "Цукерки Рошен Ромашка":"Цукерки та мармелад",
    "Сир Deli Q Daily Маасдам 45%":"Тверді, м’які та плавлені сири",
    "Сирники Valesto випечені заморожені":"Пельмені, вареники та напівфабрикати",
    "Мак.виp. 0,5 кг De Luxe Foods&Goods Selected Спіралі":"Макарони та локшина",
    "Kaвa 230г Nescafe Classic":"Кава",
    "Вepшки 250 мл Laciata":"Молоко, вершки та рослинні напої",
    "Нaпій 0,5 л Hell бeзaлкoгoльний eнepгeтичний":"Енергетичні напої",
    "Манго 100 г сушене":"Горіхи, насіння та сухофрукти",
    "Салат айсберг":"Овочі та зелень",
    "Олія 0,85л Щедрий Дар":"Олія, оцет і жири",
    "Сироп з маракуї":"Джем, варення, мед та сиропи",
}
for name,expected in cases.items():
    got=category_for(name)
    assert got==expected,(name,expected,got)
assert "nescafe" in normalize_category_text("Kaвa Nescafe")

# Check browser regex compatibility and mixed-script normalization with Node.
if shutil.which("node"):
    script=r"""
const fs=require('fs');
const rules=JSON.parse(fs.readFileSync(process.argv[1],'utf8')).rules;
const normalize=n=>String(n||'').toLowerCase().replace(/[a-zа-яіїєґ]+/gi,t=>
 /[а-яіїєґ]/i.test(t)&&/[a-z]/i.test(t)
 ?t.replace(/[aceiopxykhmbt]/gi,c=>({a:'а',c:'с',e:'е',i:'і',o:'о',p:'р',x:'х',y:'у',k:'к',h:'н',m:'м',b:'в',t:'т'}[c.toLowerCase()]||c)):t);
const compiled=rules.map(r=>({...r,re:new RegExp(r.pattern,'i'),ex:r.exclude?new RegExp(r.exclude,'i'):null}));
const classify=n=>{const s=normalize(n);return (compiled.find(r=>r.re.test(s)&&(!r.ex||!r.ex.test(s)))||{label:'Інші товари'}).label};
const names=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(names.map(classify)));
"""
    result=subprocess.run(["node","-e",script,str(ROOT/"data/category_rules.json")],
        input=json.dumps(list(cases),ensure_ascii=False),text=True,capture_output=True,check=True)
    classified=json.loads(result.stdout)
    for (name,expected),got in zip(cases.items(),classified):
        assert got==expected,("JS",name,expected,got)
# The GitHub Pages UI must use the same rule source and valid JavaScript.
html=(ROOT/"index.html").read_text(encoding="utf-8")
assert 'category_rules.json' in html and 'categoryOptions(categories)' in html
assert 'function normalizeCategoryText' in html
assert 'Уся група' in html and 'c.startsWith("group:")' in html
if shutil.which("node"):
    import tempfile
    js=html.split("<script>",1)[1].split("</script>",1)[0]
    with tempfile.TemporaryDirectory() as temp:
        output=Path(temp)/"site.js"
        output.write_text(js,encoding="utf-8")
        check=subprocess.run(["node","--check",str(output)],
             capture_output=True,text=True)
        assert check.returncode==0,check.stderr
print("PASS: detailed product categories, food/pet exclusions and JS/Python parity")
