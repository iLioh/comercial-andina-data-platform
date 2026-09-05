DELETE FROM reference.productos;
INSERT INTO reference.productos (producto, categoria) VALUES
('Laptop Pro', 'Computación'),
('Laptop Business', 'Computación'),
('Tablet 10', 'Computación'),
('Monitor 24', 'Computación'),
('Smart TV 50', 'Electrónica'),
('Smartphone 5G', 'Electrónica'),
('Audífonos Bluetooth', 'Electrónica'),
('Cámara Digital', 'Electrónica'),
('Refrigeradora', 'Electrohogar'),
('Microondas', 'Electrohogar'),
('Licuadora', 'Electrohogar'),
('Aspiradora', 'Electrohogar'),
('Impresora Multifuncional', 'Oficina'),
('Proyector', 'Oficina'),
('Teclado Inalámbrico', 'Oficina'),
('Mouse Inalámbrico', 'Oficina'),
('Silla Ergonómica', 'Muebles'),
('Escritorio Ejecutivo', 'Muebles'),
('Estante Modular', 'Muebles'),
('Archivador', 'Muebles');

DELETE FROM reference.regiones;
INSERT INTO reference.regiones (region) VALUES
('Lima'),
('Norte'),
('Sur'),
('Centro'),
('Oriente');
