# Photo Album

**The app for people who never get around to making photo albums… and for those who like knowing where their photos were taken!**

**English** | [Français](README.fr.md)

Photo Album is an application created by **Bertrand Boutillier** to make it easy to build photo albums from your own pictures, with particular attention to dates, places, and captions.

It grew out of two main ideas: making real use of the geographic information embedded in photos through **built-in reverse geocoding**, and providing an **extensible template engine** that can support different kinds of albums without locking the application into a single layout.

Designed to be highly modular, Photo Album currently includes the album templates its author actually uses himself — direct descendants of layouts he once built with bits of PHP and plenty of home-made tinkering.

After a few decades of building things for the Web, perhaps it was time to turn all of that into a proper application. It is now done, with the help of AI.

---

## Why Photo Album?

Making a photo album sounds simple until you actually have to sort the pictures, check their dates, figure out where they were taken, write captions, choose layouts, and keep the presentation consistent across dozens of pages.

Photo Album aims to automate what can reasonably be automated while keeping the user in control of the editorial decisions that shape the album.

The application analyzes photos and their metadata, helps make sense of their geographic information, lets you review and organize the resulting data, and then uses templates to compose and generate the album.

The goal is therefore not simply to “put photos into a PDF,” but to provide a tool for progressively building a coherent album from a collection of photographs.

## Highlights

### Built-in reverse geocoding

GPS coordinates recorded by cameras and smartphones are useful to a computer, but they are not particularly useful as album captions.

Photo Album includes **reverse geocoding** support to turn those coordinates into meaningful geographic information.

A single position can contain several levels of information: a landmark, road, neighborhood, hamlet, village, city, region, country, and more. Photo Album preserves that richness instead of immediately reducing a location to a single city name.

The user can then choose which geographic components are actually relevant to the album, enable or disable them, and correct the results when necessary.

Batch editing also makes it possible to efficiently apply corrections to multiple photos that share the same geographic context.

The aim is to turn raw GPS coordinates into **useful location information for an album caption**, while keeping human control over the final result.

### Extensible template engine

Photo Album is built around a **modular template engine**.

Album layout is therefore not tied to a single composition hard-coded into the application. Templates define the available layouts and allow the presentation capabilities of Photo Album to evolve without rebuilding the entire application around each new design.

The templates currently included with Photo Album are the layouts the author uses for his own albums. They are descendants of home-made layouts that were previously generated using PHP scripts.

The architecture is intended to make it possible to progressively add new layouts and, eventually, to make it easier to build collections of templates for different kinds of albums.

## Features

Photo Album can currently be used to:

- create and open album projects;
- analyze folders containing photographs;
- read useful image metadata;
- work with capture dates;
- detect available GPS coordinates;
- perform reverse geocoding;
- preserve the individual geographic components of a location;
- select the geographic information relevant to album captions;
- edit location information individually or in batches;
- add and edit photo captions;
- organize photos and album pages;
- use different page-layout templates;
- preview the album;
- generate the final document as a PDF.

The user interface is available in English and French.

## Application workflow

Building an album is organized into several stages available from the main interface.

### Photos

This section is used to import and analyze the photographs that will be used in the album.

Available metadata is examined to retrieve information such as capture dates and GPS coordinates.

### Places & Captions

This stage is used to review the editorial information associated with the photographs.

Reverse-geocoding results can be reviewed and adjusted. Individual location components can be enabled or disabled to build geographic descriptions appropriate for the album.

Batch editing makes corrections easier when several photographs share the same geographic context.

Photo captions can also be prepared and edited here.

### Album

This section defines the album's general settings and overall presentation.

It first allows you to select the **paper size** and **orientation**.

Album composition then relies on Photo Album's template engine. Templates can be selected for the different families of pages that make up an album:

- the four cover pages;
- transition pages between months or years;
- pages containing photographs;
- special-purpose pages that can be added to the album.

This approach makes it possible to change and extend the appearance and structure of an album through templates rather than by modifying the rendering engine itself.

Photo Album can also constrain the total page count to a **multiple of 4**, accommodating common album production and printing requirements.

### Plan

The plan provides an **overview of the album structure** resulting from the photographs, album settings, and selected templates.

It is not intended for manually arranging pages. Instead, it helps you understand the resulting composition and identify adjustments that may be useful.

Photo Album can highlight **unused photo slots** and provide **suggestions for pages that could be added** to achieve a more coherent composition.

The plan therefore acts as a structural review step between configuring the album and inspecting its visual rendering.

### Preview

The preview provides a **WYSIWYG** (*What You See Is What You Get*) representation of the album.

It lets you visually browse the pages as they will be rendered, including their photographs, captions, location information, and the layouts defined by the selected templates.

This provides a final visual check of the actual composition before generating the finished document.

### PDF Export

The final stage generates the **finished PDF document** corresponding to the album reviewed in the preview.

Photo Album lets you select the **quality of the generated PDF**, so the final document can be adapted to its intended use.

## Project philosophy

Photo Album tries to maintain a clear separation between:

- the **original photographs**;
- the **extracted metadata**;
- the **user's editorial choices**;
- the **album composition**;
- the **final rendering**.

This separation makes it possible to correct or reorganize an album without altering the original photo files.

The project also favors a modular architecture. Metadata handling, geocoding, composition, templates, and rendering are designed as separate responsibilities rather than as one monolithic processing pipeline.

## Architecture

The main source code lives in:

    src/photoalbum/

The project is organized into components responsible for areas including:

- project data access;
- photo and metadata analysis;
- geocoding;
- the graphical user interface;
- location-caption construction;
- page composition;
- templates;
- rendering and PDF export;
- internationalization.

This organization is intended to allow each part of the application to evolve without making templates or the user interface depend unnecessarily on the internal details of other components.

## Development

Photo Album is developed in **Python**.

The graphical user interface is built with **Qt through PySide6**.

The project also includes an automated test suite using **pytest**.

To run the tests from a configured development environment:

    pytest -q

The project provides the following command to launch the graphical application from the Python environment in which Photo Album is installed:

    pa

More detailed installation and development-environment documentation will be added as the project stabilizes.

## Internationalization

Photo Album currently provides its user interface in:

- English;
- French.

By default, the application selects its language from the system environment, with English used as the fallback language.

The interface language can also be explicitly selected at launch, which is useful both for multilingual environments and for development and testing.

## Project status

Photo Album is a personal project under active development.

It is already used to produce real photo albums, but its architecture and user interface continue to evolve.

The templates currently included primarily reflect the author's own real-world needs. The template engine itself is designed to progressively support additional layouts and use cases.

## Contributing

Feedback, bug reports, and improvement proposals are welcome.

Particular attention is given to maintaining a readable and modular architecture, especially in areas involving:

- the template engine;
- geocoding and location handling;
- album composition;
- the user interface;
- internationalization.

## License

Photo Album is free software distributed under the terms of the **GNU General Public License, version 3 or later (GPLv3+)**.

## Author

**Bertrand Boutillier**

b.boutillier@gmail.com

Photo Album was built with the help of AI by a guy who has been working on the Web for a few decades.

## Dedication

*Dedicated to my two beloved daughters, **Petit-Gâteau and Sido**. ❤️*