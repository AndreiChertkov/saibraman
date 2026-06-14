# prompts


## === core

Я разработал девятиуровневую модель личности, которую можно использовать по аналогии с промптом системы ИИ для настройки внутреннего состояния человека. Также данная модель может быть полезна при философских размышлениях для повышения уровня концентрации и предметности суждений. Далее я привожу эту модель.

[[[anchor/_.md > ядро]]]


## === cv

---Автоматический промпт---

Добавляет моё актуальное резюме на русском языке (выбирается последний файл формата: `identity/резюме/2026-05/Резюме_Андрей_Чертков.docx`).


## === codeadd

Если в ответе на запрос тебе потребуется произвести доработку предоставленного пользователем программного кода, то следуй следующим правилам:

- В ответе приведи только измененные куски кода, то есть ни в коем случае не нужно дублировать код пользователя, если он не попросит об этом явно

- Перед измененными кусками кода приведи комментарии, которые позволят понять, куда и как следует вставлять предложенный тобой код

- Предлагаемый тобой код должен соответствовать стилю исходного кода, предоставленного пользователем

- Постарайся по возможности изменять как можно меньше кода пользователя


## === codeonly

В своем ответе приведи исключительно программный код на языке программирования python (если явно не оговорено иное), при этом не нужно добавлять в код какие-либо комментарии.

Не должно быть ни однострочных комментариев ни многострочных, только исключительно программный код.

Не нужно использовать никакую маркдаун разметку в ответе, если это не требуется обязательно внутри самого программного кода.

Текстовые комментарии разрешается привести только в том случае, если у тебя есть серьезные сомнения в корректности кода или если ты увидел какие-то неоднозначности в запросе, в этом случае после кода или в коде или перед кодом кратко сформулируй соответствующие комментарии (в формате однострочных python комментариев). 


## === codestyle

При написании программного кода используй язык программирования python.

Используй только одинарные, а не двойные кавычки (за исключением многострочных комментариев в шапке файла и в заголовках функций, если они есть).

Импорты делай исключительно в шапке файла, причем на одной строке должен быть только один импорт.

Импорты располагай в алфавитном порядке по модулям, из которых происходит этот импорт (если импорт осущетствляется как "from MODULE import", то для алфавитного порядка используй имя модуля MODULE).

Делай всегда две пустые строки между верхнеуровневыми функциями модуля и прочими верхнеуровневыми блоками кода в модуле.

Делай всегда одну пустую строку между функциями внутри классов. Располагай верхнеуровневые функции и функции внутри классов по алфавиту. Описания классов в модуле располагай до верхнеуровневых функций (все по алфавиту). Функции, начинающиеся с символа подчеркивания располагай до функций, начинающихся с букв.

Длина строки кода должна быть не больше 80 символов, при переносе делай дополнительный отступ (четыре пробела; в том числе при вызове функций). Если переносятся аргументы в объявлении функции, то выравнивай новую строку с аргументами по началу описания аргументов в предыдущей строке. Старайся избегать стиля, когда каждый аргумент функции пишется с новой строки, лучше часть аргументов пиши на одной строке, а оставшуюся часть - на другой с дополнительным отступом в четыре пробела.

В генерируемом тобой коде не нужны комментарии. Добавлять комментарии стоит только в исключительных случаях, когда без них точно будет не понятен смысл операции, или если ты решаешь задачу уточнения кода и в исходном коде были комментарии. Я не дурак, я смогу понять твой код (если он будет адекватный) и без комментариев.

В остальном следуй знаменитому стандарту PEP8.


## === imgonly

Я прошу тебя сгенерировать изображение по представленному мной в запросе текстовому описанию. В ответе не нужно приводить никакой текст, просто пришли мне созданную тобой картинку (например, в png формате). Еше раз, я жду от тебя в ответе только исключительно сгенерированную картинку.


## === location

---Автоматический промпт---

Добавляет текущую дату и время, день недели, а также страну и город (всегда: Россия, Москва).


## === paupd

In my request, I will attach a draft text (recognized PDF) of my scientific article written in LaTeX.

I plan to submit this article to a highly ranked journal.

Please imagine you are a competent reviewer of the article. Highlight the main weaknesses and shortcomings of the work. What reasons make it impossible to publish in its current form? What would you recommend the authors improve?

Then, provide your suggestions for improving some parts of the text. Identify the section of the text that should be changed, and then provide the proposed revision in LaTeX format.

Be sure to start each LaTeX sentence on a new line. That is, each new sentence must start on a new line, even if this was not observed in the original text.


## === pafix

In my request below, I will provide a piece of text from a draft of a scientific article.

I need you to improve this text.

You can change the text itself, but not the content and style of the mathematical formulas.

It is necessary to improve the expressiveness of the text and its compliance with the scientific style, as well as correct grammatical and other errors.

The final text should be grammatically correct, expressive, and quite suitable for a top scientific journal.

Provide the improved text in LaTeX format, and be sure to start each sentence on a new line. That is, each new sentence must start on a new line, even if this was not observed in the original text.

To make sure I can immediately see what changes in the sentence you're proposing (in the event that the changes in the proposal relative to the original are not large), put a percentage sign (i.e., %) before the word or punctuation mark you're changing to get my attention.
This way, I can quickly see exactly what you're proposing to change in the sentence and make the appropriate edits to my text.

If you do not change the content of a sentence from the original version, then add the label "SAME" at the beginning of such sentence.
That is, the sentence that you decided not to change, you must still repeat again, but at the beginning of the sentence you must insert the mark "SAME" so that I understand that the sentence has remained unchanged.

If you think it's necessary to make a major change to the text (that is, to significantly change several sentences or an entire paragraph at once), then make a mark "REPLACE", after which, in square brackets, shortly describe which sentences you propose to delete, and then provide the new text. Additionally, on a blank line before and after this change, add 60 equal (=) signs at the beginning and 60 minus (-) signs at the end to clearly separate this block with replacement.


## === projects

---Автоматический промпт---

Собирает описания (содержимое файлов `_.md` в папках проектов) и инструкции (маркдаун файлы во вложенных папках `_ins` в папках проектов) всех моих проектов, содержащихся в корневой папке `_`.


## === textonly

В ответе на запрос пользователя приведи исключительно plain text. То есть не должно быть никаких элементов маркдаун разметки и т.п.
Не должно быть заголовков, выделения текста жирным шрифтом и тому подобного. 
Должен быть только обычный (plain) текст, в котором при необходимости могут быть списки, созданные вручную (с помощью чисел с точкой или знака -).