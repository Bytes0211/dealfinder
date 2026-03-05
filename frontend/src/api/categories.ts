/** Top-level deal categories (sourced from developer/categories.md). */
export const CATEGORIES: string[] = [
  'Electronics',
  'Computers & Office',
  'Clothing & Apparel',
  'Shoes',
  'Home & Kitchen',
  'Appliances',
  'Beauty & Personal Care',
  'Health & Wellness',
  'Sports & Outdoors',
  'Toys & Games',
  'Baby Products',
  'Automotive',
  'Tools & Home Improvement',
  'Pet Supplies',
  'Grocery',
  'Books, Movies & Media',
  'Office & School Supplies',
  'Jewelry & Watches',
  'Arts, Crafts & DIY',
  'Miscellaneous',
];

/** Subcategory map keyed by top-level category (sourced from developer/categories.md).
 *  Empty array means no subcategories defined for that category.
 */
export const CATEGORY_MAP: Record<string, string[]> = {
  'Electronics': [
    'Phones & Smartphones', 'Phone Accessories', 'Laptops', 'Desktops & PC Components',
    'Tablets & eReaders', 'Headphones & Earbuds', 'Speakers & Audio Systems',
    'TVs & Home Theater', 'Cameras & Photography', 'Wearables',
    'Gaming Consoles & Accessories', 'Networking',
  ],
  'Computers & Office': [
    'Monitors', 'Keyboards & Mice', 'Printers & Scanners', 'Storage',
    'Office Supplies', 'Software', 'PC Parts',
  ],
  'Clothing & Apparel': ['Men', 'Women', 'Kids'],
  'Shoes': ['Men', 'Women', 'Kids', 'Athletic', 'Boots', 'Sandals'],
  'Home & Kitchen': [
    'Furniture', 'Bedding', 'Kitchen Appliances', 'Cookware & Utensils',
    'Home Decor', 'Storage & Organization', 'Cleaning Supplies', 'Lighting',
  ],
  'Appliances': ['Large Appliances', 'Small Appliances'],
  'Beauty & Personal Care': [
    'Skincare', 'Haircare', 'Makeup', 'Fragrances', 'Grooming Tools', 'Oral Care',
  ],
  'Health & Wellness': [
    'Supplements', 'Medical Supplies', 'Fitness Equipment', 'Personal Care Devices',
  ],
  'Sports & Outdoors': [
    'Exercise Equipment', 'Outdoor Gear', 'Camping & Hiking',
    'Bicycles & Accessories', 'Team Sports', 'Fishing & Hunting',
  ],
  'Toys & Games': [
    'Action Figures', 'Board Games', 'Puzzles', 'Outdoor Toys',
    'Educational Toys', 'Video Games',
  ],
  'Baby Products': ['Diapers', 'Feeding', 'Strollers', 'Car Seats', 'Nursery Furniture'],
  'Automotive': [
    'Car Electronics', 'Tools & Equipment', 'Replacement Parts', 'Tires & Wheels', 'Car Care',
  ],
  'Tools & Home Improvement': [
    'Power Tools', 'Hand Tools', 'Electrical', 'Plumbing', 'Hardware', 'Smart Home Devices',
  ],
  'Pet Supplies': ['Dog', 'Cat', 'Fish & Aquatic', 'Small Animals', 'Pet Food'],
  'Grocery': [
    'Pantry Staples', 'Snacks', 'Beverages', 'Household Essentials', 'Organic & Specialty',
  ],
  'Books, Movies & Media': ['Books', 'eBooks', 'Movies & TV', 'Music', 'Video Games'],
  'Office & School Supplies': ['Stationery', 'Writing Tools', 'Backpacks', 'Classroom Supplies'],
  'Jewelry & Watches': ['Men', 'Women', 'Watches', 'Fine Jewelry'],
  'Arts, Crafts & DIY': ['Craft Supplies', 'Art Tools', 'Sewing & Fabric', 'DIY Kits'],
  'Miscellaneous': ['Seasonal', 'Gifts', 'Collectibles', 'Clearance'],
};
