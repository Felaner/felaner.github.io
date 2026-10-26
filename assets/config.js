// Разделы вики. Категории, перечисленные здесь, показываются всегда;
// категории, найденные парсером, добавляются из файлов data/<id>.js.
window.BR_CONFIG = {
  sections: [
    {
      id: "equipment",
      title: "Экипировка",
      categories: []
    },
    {
      id: "pets",
      title: "Питомцы",
      categories: []
    },
    {
      id: "mobs",
      title: "Противники",
      categories: [
        { id: "normal", name: "Обычные" },
        { id: "elite", name: "Элита" },
        { id: "bosses", name: "Боссы" },
        { id: "champions", name: "Чемпионы" }
      ]
    },
    {
      id: "items",
      title: "Предметы",
      categories: []
    },
    {
      id: "npc",
      title: "НПС",
      categories: []
    },
    {
      id: "skills",
      title: "Навыки",
      categories: []
    },
    {
      id: "guides",
      title: "Статьи",
      categories: []
    }
  ]
};
