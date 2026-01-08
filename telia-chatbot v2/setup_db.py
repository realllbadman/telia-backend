import sqlite3

DATABASE_NAME = "setup.db" 
def setup_database():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS products;")

    cursor.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price_cfa INTEGER NOT NULL,
            image_url TEXT
        );
    """)


    laptop_data = [
        ('Laptop', 'Used Dell Latitude 3380', 'Reliable business laptop, Intel Core i3-6th Gen, 8GB RAM, 256GB SSD. Good for office work.', 115000, 'https://th.bing.com/th/id/OIP.usWvy39_mi-e8zasABi7yQHaHa?w=181&h=181&c=7&r=0&o=7&cb=ucfimg2&dpr=1.5&pid=1.7&rm=3&ucfimg=1'),
        ('Laptop', 'Used HP ProBook 430 G3', 'Sleek silver design, Intel Core i5-6th Gen, 8GB RAM, 128GB SSD. Good for general use.', 125000, 'https://th.bing.com/th/id/OIP.Txz0-EByqTOFH01sKqUmSQHaFj?w=206&h=180&c=7&r=0&o=7&cb=ucfimg2&dpr=1.5&pid=1.7&rm=3&ucfimg=1') 
        ]

    tool_data = [
        ('Tool', 'Electric Rotary Drill', 'Powerful 650W drill with hammer function. Ideal for drilling holes in wood, metal, and concrete.', 45000, 'https://tse3.mm.bing.net/th/id/OIP.1o0HSJhiT_bkQNt1PUaeTQHaHa?cb=ucfimg2&ucfimg=1&rs=1&pid=ImgDetMain&o=7&rm=3'),
        ('Tool', 'Cordless Screwdriver Set', 'Lightweight 12V screwdriver with multiple bits. Best for assembling furniture and light repairs.', 25000, 'https://th.bing.com/th/id/OIP.zmfl4kANrjtspd_wMUx0DgHaHa?w=206&h=206&c=7&r=0&o=7&cb=ucfimg2&dpr=1.5&pid=1.7&rm=3&ucfimg=1'),
    ]
    
    
    phone_data = [
        ('Phone', 'Samsung Galaxy Flip 4', 'A compact foldable smartphone with high-end features, Snapdragon 8+ Gen 1 processor, and good camera capabilities.', 98000, 'https://th.bing.com/th/id/OIP.VrDmsxQlDvHlJcmeG1S7AQHaFj?w=200&h=180&c=7&r=0&o=7&cb=ucfimg2&dpr=1.5&pid=1.7&rm=3&ucfimg=1'),
        ('Phone', 'Iphone 16 pro', 'High-end phone with A18 Pro chip, advanced camera, and titanium design.', 760000, 'https://tse1.mm.bing.net/th/id/OIP.4rUOdiyaL-F62t7ETBsO1AHaHa?cb=ucfimg2&ucfimg=1&rs=1&pid=ImgDetMain&o=7&rm=3'),
        ('Phone', 'Infinix Note 30', 'A budget-friendly smartphone with a large display and excellent battery life, ideal for general daily use.', 80000, 'https://th.bing.com/th/id/OIP.0u6sPWeUAEtvmYxYZj5oZQHaHa?w=170&h=180&c=7&r=0&o=7&cb=ucfimg2&dpr=1.5&pid=1.7&rm=3&ucfimg=1'),
        ('Phone', 'Tecno Spark 8', 'Ultra-cheap entry-level phone. Reliable for calls and basic messaging.', 65000, 'https://tse4.mm.bing.net/th/id/OIP.BKrV5shILAa8LVlpgsl7aAHaHa?cb=ucfimg2&ucfimg=1&rs=1&pid=ImgDetMain&o=7&rm=3'),
    ]

    all_products = laptop_data + tool_data + phone_data

    cursor.executemany(
        "INSERT INTO products (category, name, description, price_cfa, image_url) VALUES (?, ?, ?, ?, ?)",
        all_products
    )

    conn.commit()
    conn.close()
    print(f"Database '{DATABASE_NAME}' created and populated successfully!")

if __name__ == "__main__":
    setup_database()