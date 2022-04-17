import re
from typing import List, Dict
import requests
import bs4

import collections

collections.Callable = collections.abc.Callable


class RecipeItem:
    def __init__(self, item, quantity):
        self.item: Item = item
        self.quantity: float = quantity

    def __str__(self):
        return "\t\t\t{} x {}\n".format(self.item.name, self.quantity)


class Recipe:
    def __init__(self, name, inputs, outputs, time, alternative):
        self.name: str = name
        self.inputs: List[RecipeItem] = inputs
        self.outputs: List[RecipeItem] = outputs
        self.time = time
        self.alternative = alternative

    def add_input(self, item: RecipeItem):
        self.inputs.append(item)

    def add_output(self, item: RecipeItem):
        self.outputs.append(item)

    def get_input_items(self) -> List[str]:
        out = []
        for recItem in self.inputs:
            out.append(recItem.item.id)
        return out

    def get_output_items(self) -> List[str]:
        out = []
        for recItem in self.outputs:
            out.append(recItem.item.id)
        return out

    def __str__(self):
        inputs_str = ""
        for part in self.inputs:
            inputs_str += str(part)

        outputs_str = ""
        for part in self.outputs:
            outputs_str += str(part)

        return "\tRecipe Name: {}\n\t\tInputs: \n{}\n\t\tOutputs: " \
               "\n{}\n\t\tTime: {}\n\t\tAlt: {}\n".format(self.name,
                                                          inputs_str,
                                                          outputs_str,
                                                          self.time,
                                                          self.alternative)


class Item:
    def __init__(self, item_id, link, item_name):
        self.id = item_id
        self.name = item_name
        self.link = link
        self.recipes: List[Recipe] = []

    def add_recipe(self, recipe: Recipe):
        self.recipes.append(recipe)

    def __str__(self):
        recipes_str = ""
        for rec in self.recipes:
            recipes_str += str(rec) + "\n"

        return "Item id: {}\nItem name: {}\nItem link: {}\nRecipes: \n{}\n\n".format(self.id, self.name, self.link,
                                                                                     recipes_str)


class ItemList:
    items: Dict[str, Item] = {}

    def add_item(self, item: Item):
        self.items[item.id] = item

    def get_item(self, item_id: str) -> Item:
        try:
            return self.items[item_id]
        except KeyError:
            self.add_item(Item(item_id, "https://satisfactory.fandom.com/wiki/" + item_id, item_id.replace("_", " ")))
            return self.get_item(item_id)

    def get_all_items(self) -> List[Item]:
        return list(self.items.values())

    def get_all_ids(self) -> List[str]:
        return list(self.items.keys())

    def __str__(self):
        out = ""
        for item in self.get_all_items():
            out += str(item)
        return out


class Parser:
    itemList = ItemList()

    def parse_item_list(self):
        items_file = open("item_list.html", 'r')
        for line in items_file:
            item_re = re.compile(r'<a href="(?P<LINK>[a-zA-Z/_\-:]*)" title="(?P<NAME>[A-Za-z\-_ ]*)">')
            search = item_re.search(line)
            link = search.group("LINK")
            name = search.group("NAME")
            item_id = link.replace("/wiki/", "")
            link = "https://satisfactory.fandom.com" + link
            item = Item(item_id, link, name)
            self.itemList.add_item(item)

    def parse_items_recipes(self):
        for item in self.itemList.get_all_items():
            self._parse_item_recipes(item)

    def _parse_item_recipes(self, item: Item):
        item_html = requests.get(item.link).text
        page_re = re.compile(
            r'(?P<TABLE><tbody><tr><th>Recipe</th><th colspan="12">Ingredients</th><th>Building</th><th '
            r'colspan="2">Products</th><th>Prerequisites</th></tr>[\w\W\s]*?)</table>')
        try:
            table = "<table>" + page_re.search(item_html).group("TABLE") + "</table>"
        except AttributeError:
            return

        soup = bs4.BeautifulSoup(table, "html.parser")

        whitelist_tag = ['table', 'tbody', 'tr', 'td', 'th', 'span', 'a']
        whitelist_attr = ["href"]
        for tag in soup.find_all(True):
            if tag.name not in whitelist_tag:
                tag.attrs = {}
            else:
                attrs = dict(tag.attrs)
                for attr in attrs:
                    if attr not in whitelist_attr:
                        del tag.attrs[attr]

        html1 = str(soup)
        html1 = html1.replace("<div>", "").replace("</div>", "")
        html1 = html1.replace("<table>", "").replace("</table>", "")
        html1 = html1.replace("<tbody>", "").replace("</tbody>", "")

        table_rows_str = html1.split("</tr><tr>")[1:]
        table_rows_str[-1] = table_rows_str[-1].replace("</tr>", "")

        table_rows: List[List[str]] = []
        for i in range(len(table_rows_str)):
            if table_rows_str[i].startswith("<td><span>"):
                continue
            if (i + 1) < len(table_rows_str) and table_rows_str[i + 1].startswith("<td><span>"):
                table_rows_str[i] = table_rows_str[i].replace("</span></td><td><span><a",
                                                              "</span></td>" + table_rows_str[i + 1] + "<td><span><a",
                                                              1)
            cols = table_rows_str[i].split("</td><td>")
            cols[0] = cols[0].replace("<td>", "")
            cols[-1] = cols[-1].replace("</td>", "")
            table_rows.append(cols[:-1])

        for row in table_rows:
            rec_name = row[0]
            alternate = False
            if "Alternate" in rec_name:
                rec_name = rec_name.replace("Alternate: ", "")
                rec_name = rec_name.replace('<br/><span><a href="/wiki/Hard_Drive">Alternate</a></span>', '')
                alternate = True
            inputs = []
            outputs = []
            time = 0.0
            in_inputs = True
            for col in row[1:]:
                if col.startswith("<span><a href"):
                    in_inputs = False
                    time_re = re.compile(r'</a></span><br/>(?P<TIME>\d*) sec')
                    try:
                        time = int(time_re.search(col).group("TIME"))
                    except AttributeError:
                        pass
                else:
                    if len(col) > 5:
                        part_re = re.compile(
                            r'<span>(?P<QTY>[\d.]*) × </span><a href="/wiki/(?P<ID>[a-zA-Z_\-]*)"><img/></a><br/>')
                        part_search = part_re.search(col)
                        item_id = part_search.group("ID")
                        item_qty = float(part_search.group("QTY"))
                        if in_inputs:
                            inputs.append(RecipeItem(self.itemList.get_item(item_id), item_qty))
                        else:
                            outputs.append(RecipeItem(self.itemList.get_item(item_id), item_qty))
            item.add_recipe(Recipe(rec_name, inputs, outputs, time, alternate))


def main():
    parser = Parser()
    # item = Item('aaa', "https://satisfactory.fandom.com/wiki/Aluminum_Casing", "aaAAaa")
    parser.parse_item_list()
    parser.parse_items_recipes()
    print(parser.itemList)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()
