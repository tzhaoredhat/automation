#
# Copyright (c) 2015 Red Hat
# Licensed under The MIT License (MIT)
# http://opensource.org/licenses/MIT
#
import json

from django.shortcuts import render, get_object_or_404
from django.conf import settings
from kobo.django.views.generic import DetailView, SearchView
from rest_framework import viewsets, mixins, status
from rest_framework.response import Response

from . import filters
from . import signals
from . import models
from .forms import (ReleaseSearchForm, BaseProductSearchForm,
                    ProductSearchForm, ProductVersionSearchForm)
from .serializers import (ProductSerializer, ProductVersionSerializer,
                          ReleaseSerializer, BaseProductSerializer,
                          ReleaseTypeSerializer, ReleaseVariantSerializer,
                          VariantTypeSerializer)
from pdc.apps.repository import models as repo_models
from pdc.apps.common.viewsets import (ChangeSetModelMixin,
                                      ChangeSetCreateModelMixin,
                                      ChangeSetUpdateModelMixin,
                                      MultiLookupFieldMixin,
                                      StrictQueryParamMixin)
from . import lib


class ReleaseListView(SearchView):
    form_class = ReleaseSearchForm
    queryset = models.Release.objects.select_related('release_type', 'product_version', 'base_product').order_by('id')
    allow_empty = True
    template_name = "release_list.html"
    context_object_name = "release_list"
    paginate_by = settings.ITEMS_PER_PAGE


class ReleaseDetailView(DetailView):
    queryset = models.Release.objects.select_related('release_type') \
        .prefetch_related('variant_set__variant_type',
                          'variant_set__variantarch_set__arch')
    pk_url_kwarg = "id"
    template_name = "release_detail.html"

    def get_context_data(self, **kwargs):
        context = super(ReleaseDetailView, self).get_context_data(**kwargs)
        context['repos'] = repo_models.Repo.objects.filter(
            variant_arch__variant__release=self.object
        ).select_related('variant_arch', 'variant_arch__arch',
                         'content_category', 'content_format', 'repo_family', 'service')
        return context


class BaseProductListView(SearchView):
    form_class = BaseProductSearchForm
    queryset = models.BaseProduct.objects.all().order_by('id')
    allow_empty = True
    template_name = "base_product_list.html"
    context_object_name = "base_product_list"
    paginate_by = settings.ITEMS_PER_PAGE


class BaseProductDetailView(DetailView):
    model = models.BaseProduct
    pk_url_kwarg = "id"
    template_name = "base_product_detail.html"
    context_object_name = "base_product"

    def get_context_data(self, **kwargs):
        context = super(BaseProductDetailView, self).get_context_data(**kwargs)
        context["release_list"] = models.Release.objects.filter(
            base_product=self.object.id
        ).select_related('product_version', 'base_product', 'release_type')
        return context


class ProductListView(SearchView):
    form_class = ProductSearchForm
    queryset = models.Product.objects.prefetch_related('productversion_set__release_set').order_by('id')
    allow_empty = True
    template_name = "product_list.html"
    context_object_name = "product_list"
    paginate_by = settings.ITEMS_PER_PAGE


class ProductDetailView(DetailView):
    queryset = models.Product.objects.prefetch_related('productversion_set__release_set')
    pk_url_kwarg = "id"
    template_name = "product_detail.html"
    context_object_name = "product"


class ProductViewSet(ChangeSetCreateModelMixin,
                     ChangeSetUpdateModelMixin,
                     StrictQueryParamMixin,
                     mixins.RetrieveModelMixin,
                     mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """
    API endpoint that allows products to be viewed or edited.

    Each product can have multiple version. Their identifiers are provided in
    the form of `product_version_id` (both in requests and responses).
    """

    queryset = models.Product.objects.prefetch_related('productversion_set').order_by('id')
    serializer_class = ProductSerializer
    lookup_field = 'short'
    filter_class = filters.ProductFilter

    def create(self, *args, **kwargs):
        """
        __Method__: POST

        __URL__: $LINK:product-list$

        __Data__:

        %(WRITABLE_SERIALIZER)s

        __Response__:

        %(SERIALIZER)s
        """
        return super(ProductViewSet, self).create(*args, **kwargs)

    def retrieve(self, *args, **kwargs):
        """
        __Method__: GET

        __URL__: $LINK:product-detail:short$

        __Response__:

        %(SERIALIZER)s
        """
        return super(ProductViewSet, self).retrieve(*args, **kwargs)

    def list(self, *args, **kwargs):
        """
        __Method__: GET

        __URL__: $LINK:product-list$

        __Query params__:

        %(FILTERS)s

        __Response__: a paged list of following objects

        %(SERIALIZER)s
        """
        return super(ProductViewSet, self).list(*args, **kwargs)

    def update(self, *args, **kwargs):
        """
        __Method__: PUT, PATCH

        __URL__: $LINK:product-detail:short$

        __Data__:

        %(WRITABLE_SERIALIZER)s

        Please note that if you update the `short` field, the URL of this
        product will change. The change of short name is *not* propagated to
        product versions nor releases.

        __Response__:

        %(SERIALIZER)s
        """
        return super(ProductViewSet, self).update(*args, **kwargs)


class ProductVersionViewSet(ChangeSetCreateModelMixin,
                            ChangeSetUpdateModelMixin,
                            StrictQueryParamMixin,
                            mixins.RetrieveModelMixin,
                            mixins.ListModelMixin,
                            viewsets.GenericViewSet):
    """
    API endpoint that allows product versions to be viewed or edited.

    Product versions always refer to a product by means of a human readable
    `short` name. Similarly releases are referenced by `release_id`. This
    applies to both requests and responses.
    """
    queryset = models.ProductVersion.objects.select_related('product').prefetch_related('release_set').order_by('id')
    serializer_class = ProductVersionSerializer
    lookup_field = 'product_version_id'
    lookup_value_regex = '[^/]+'
    filter_class = filters.ProductVersionFilter

    def create(self, *args, **kwargs):
        """
        __Method__: POST

        __URL__: $LINK:productversion-list$

        __Data__:

        %(WRITABLE_SERIALIZER)s

        If `short` is not specified, the short name of associated product will
        be used.

        __Response__:

        %(SERIALIZER)s
        """
        return super(ProductVersionViewSet, self).create(*args, **kwargs)

    def retrieve(self, *args, **kwargs):
        """
        __Method__: GET

        __URL__: $LINK:productversion-detail:product_version_id$

        __Response__:

        %(SERIALIZER)s

        The list of releases is ordered by short and version.
        """
        return super(ProductVersionViewSet, self).retrieve(*args, **kwargs)

    def list(self, *args, **kwargs):
        """
        __Method__: GET

        __URL__: $LINK:productversion-list$

        __Query params__:

        %(FILTERS)s

        __Response__: a paged list of following objects

        %(SERIALIZER)s

        The list of releases for each product version is ordered by short and
        version.
        """
        return super(ProductVersionViewSet, self).list(*args, **kwargs)

    def update(self, *args, **kwargs):
        """
        __Method__: PUT, PATCH

        __URL__: $LINK:productversion-detail:product_version_id$

        __Data__:

        %(WRITABLE_SERIALIZER)s

        Please note that if you change the `short` or `version` field, the
        `product_version_id` will be modified accordingly, and the URL of the
        object will be changed. All changes are local to the updated model and
        are not propagated to associated releases.

        __Response__:

        %(SERIALIZER)s
        """
        return super(ProductVersionViewSet, self).update(*args, **kwargs)


class ReleaseViewSet(ChangeSetCreateModelMixin,
                     ChangeSetUpdateModelMixin,
                     StrictQueryParamMixin,
                     mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    An API endpoint providing access to releases.

    Each release can reference either a product version or a base product (or
    both). There references are done via human-readable `product_version_id` or
    `base_product_id`. Composes belonging to given release are referenced via
    `compose_id`.

    The list of associated composes includes both composes built for the
    particular release as well as composes linked to it. It is possible to
    distinguish between these cases by retrieving a detail of the compose.
    """
    queryset = models.Release.objects \
                     .select_related('product_version', 'release_type', 'base_product') \
                     .prefetch_related('compose_set').order_by('id')
    serializer_class = ReleaseSerializer
    lookup_field = 'release_id'
    lookup_value_regex = '[^/]+'
    filter_class = filters.ReleaseFilter

    def filter_queryset(self, qs):
        """
        If the viewset instance has attribute `order_queryset` set to True,
        this method returns a list of releases ordered by version. Otherwise it
        will return an unsorted queryset. (It is not possible to sort
        unconditionally as get_object() will at some point call this method and
        fail unless it receives a QuerySet instance.)
        """
        qs = super(ReleaseViewSet, self).filter_queryset(qs)
        if getattr(self, 'order_queryset', False):
            return sorted(qs, key=models.Release.version_sort_key)
        return qs

    def create(self, request, *args, **kwargs):
        """
        Instead of creating a release through this method, please consider
        using the $LINK:releaseclone-list$ API that will clone an existing
        release with its variants and components.

        __Method__: POST

        __URL__: $LINK:release-list$

        __Data__:

        %(WRITABLE_SERIALIZER)s

        *release_type*: $LINK:releasetype-list$

        __Response__:

        %(SERIALIZER)s
        """
        response = super(ReleaseViewSet, self).create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            signals.release_post_update.send(sender=self.object.__class__,
                                             release=self.object,
                                             request=request)
        return response

    def retrieve(self, *args, **kwargs):
        """
        __Method__: GET

        __URL__: $LINK:release-detail:release_id$

        __Response__:

        %(SERIALIZER)s

        The list of composes is ordered by their date, type and respin (even
        though those fields are not directly visible here).
        """
        return super(ReleaseViewSet, self).retrieve(*args, **kwargs)

    def list(self, *args, **kwargs):
        """
        __Method__: GET

        __URL__: $LINK:release-list$

        __Query params__:

        %(FILTERS)s

        __Response__: a paged list of following objects

        %(SERIALIZER)s

        The list of composes for each release is ordered by their date, type,
        and respin (even though those fields are not directly visible here).

        The releases themselves are ordered by short and version.
        """
        self.order_queryset = True
        return super(ReleaseViewSet, self).list(*args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        This end-point allows updating a release.

        When using the `PUT` method, if an optional field is not specified in
        the input, it will be erased.

        This applies also to Bugzilla and DistGit mapping: if it is not specified,
        it will be cleared.

        __Method__: PUT, PATCH

        __URL__: $LINK:release-detail:release_id$

        __Data__:

        %(WRITABLE_SERIALIZER)s

        Please note that if you change the `short`, `version`, `release_type`
        or `base_product` fields, the `release_id` will be updated and the URL
        of this release will change.

        __Response__:

        %(SERIALIZER)s
        """
        object = self.get_object()
        signals.release_pre_update.send(sender=object.__class__, release=object, request=request)
        response = super(ReleaseViewSet, self).update(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            signals.release_post_update.send(sender=object.__class__,
                                             release=self.object,
                                             request=request)
        return response


class ReleaseImportView(StrictQueryParamMixin, viewsets.GenericViewSet):
    queryset = models.Release.objects.none()   # Required for permissions

    def create(self, request):
        """
        Import release including variants and architectures from composeinfo
        json file.

        The input to this call is a compose info file in JSON format. The
        imported file will be parsed and required objects created in database.

        The created objects are *BaseProduct*, *Product*, *ProductVersion*,
        *Release* and its *Variant.Arch* mapping. Note that despite the input
        being a composeinfo file, no Compose object will be ever created by
        this call.

        If the created objects already exist, nothing is done with them.
        Therefore this call is idempotent and uploading the same composeinfo
        data twice is safe.

        __Method__: POST

        __URL__: $LINK:releaseimportcomposeinfo-list$

        __Data__: composeinfo data as saved in `composeinfo.json` file (the
        formatting of the file is not important for PDC, and it is possible to
        significantly minimize size of the file by removing indentation)

        __Example__:

            $ curl -H 'Content-Type: application/json' -X POST -d @/path/to/composeinfo.json \\
                "$URL:releaseimportcomposeinfo-list$"
        """
        if not request.data:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': 'Missing composeinfo'})
        lib.release__import_from_composeinfo(request, request.data)
        return Response(status=status.HTTP_201_CREATED)


class BaseProductViewSet(ChangeSetCreateModelMixin,
                         ChangeSetUpdateModelMixin,
                         StrictQueryParamMixin,
                         mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):
    """
    An API endpoint providing access to base products.
    """
    queryset = models.BaseProduct.objects.all().order_by('id')
    serializer_class = BaseProductSerializer
    lookup_field = 'base_product_id'
    lookup_value_regex = '[^/]+'
    filter_fields = ('base_product_id', 'name', 'short', 'version')

    def create(self, *args, **kwargs):
        """
        __Method__: POST

        __URL__: $LINK:baseproduct-list$

        __Data__:

        %(WRITABLE_SERIALIZER)s

        __Response__:

        %(SERIALIZER)s
        """
        return super(BaseProductViewSet, self).create(*args, **kwargs)

    def retrieve(self, *args, **kwargs):
        """
        __Method__: GET

        __URL__: $LINK:baseproduct-detail:base_product_id$

        __Response__:

        %(SERIALIZER)s
        """
        return super(BaseProductViewSet, self).retrieve(*args, **kwargs)

    def list(self, *args, **kwargs):
        """
        __Method__: GET

        __URL__: $LINK:baseproduct-list$

        __Query params__:

        %(FILTERS)s

        __Response__: a paged list of following objects

        %(SERIALIZER)s
        """
        return super(BaseProductViewSet, self).list(*args, **kwargs)

    def update(self, *args, **kwargs):
        """
        __Method__: PUT, PATCH

        __URL__: $LINK:baseproduct-detail:base_product_id$

        __Data__:

        %(WRITABLE_SERIALIZER)s

        __Response__:

        %(SERIALIZER)s
        """
        return super(BaseProductViewSet, self).update(*args, **kwargs)


class ProductVersionListView(SearchView):
    form_class = ProductVersionSearchForm
    queryset = models.ProductVersion.objects.prefetch_related('release_set').order_by('id')
    allow_empty = True
    template_name = "product_version_list.html"
    context_object_name = "product_version_list"
    paginate_by = settings.ITEMS_PER_PAGE


class ProductVersionDetailView(DetailView):
    queryset = models.ProductVersion.objects.prefetch_related('release_set__release_type')
    pk_url_kwarg = "id"
    template_name = "product_version_detail.html"
    context_object_name = "product_version"


def product_pages(request):
    return render(request, "product_pages.html", {})


class ReleaseCloneViewSet(StrictQueryParamMixin, viewsets.GenericViewSet):
    queryset = models.Release.objects.none()   # Required for permissions

    def create(self, request):
        """
        Clone an existing release identified by `old_release_id`. Currently the
        release, its variants and arches will be cloned. Also, all release
        components associated with the release will be cloned.

        __Method__: POST

        __URL__: $LINK:releaseclone-list$

        __Data__:

            {
                "old_release_id":               string,
                "short":                        string,     # optional
                "version":                      string,     # optional
                "name":                         string,     # optional
                "release_type":                 string,     # optional
                "base_product":                 string,     # optional
                "active":                       bool,       # optional
                "product_version":              string,     # optional
                "dist_git": {
                    "branch":                   string
                },                                          # optional
                "bugzilla": {
                    "product":                  string
                },                                          # optional
                "component_dist_git_branch":    string,     # optional
                "include_inactive":             bool,       # optional
                "include_trees":                [string],   # optional
                "integrated_with:               string      # optional
            }

        The changed attributes must yield a different release_id, therefore
        change in at least one of `short`, `version`, `base_product` or
        `release_type` is required.

        If `component_dist_git_branch` is present, it will be set for all
        release components under the newly created release. If missing, release
        components will be cloned without changes.

        If `include_inactive` is False, the inactive release_components belong to
        the old release won't be cloned to new release.
        Default it will clone all release_components to new release.

        If `include_tree` is specified, it should contain a list of
        Variant.Arch pairs that should be cloned. If not given, all trees will
        be cloned. If the list is empty, no trees will be cloned.
        """
        data = request.data
        if 'old_release_id' not in data:
            return Response({'__all__': 'Missing old_release_id'},
                            status=status.HTTP_400_BAD_REQUEST)
        old_release_id = data.pop('old_release_id')
        old_release = get_object_or_404(models.Release, release_id=old_release_id)

        old_data = ReleaseSerializer(instance=old_release).data

        for (field_name, field) in ReleaseSerializer().fields.iteritems():
            if not field.read_only and field_name not in data:
                value = old_data.get(field_name, None)
                if value:
                    data[field_name] = value

        for key in data.keys():
            if data[key] is None:
                data.pop(key)

        serializer = ReleaseSerializer(data=data,
                                       extra_fields=['include_trees',
                                                     'include_inactive',
                                                     'component_dist_git_branch'])
        serializer.is_valid(raise_exception=True)

        new_release = serializer.save()
        request.changeset.add('Release', new_release.pk,
                              'null', json.dumps(new_release.export()))

        signals.release_clone.send(sender=new_release.__class__,
                                   request=request,
                                   original_release=old_release,
                                   release=new_release)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ReleaseRPMMappingView(StrictQueryParamMixin, viewsets.GenericViewSet):
    lookup_field = 'package'
    queryset = models.Release.objects.none()   # Required for permissions
    extra_query_params = ['disable_overrides']

    def retrieve(self, request, **kwargs):
        """
        __URL__: $LINK:releaserpmmapping-detail:release_id:package$

        Returns a JSON representing the RPM mapping of the latest compose for
        given release. There is an optional query parameter
        `?disable_overrides=1` which returns the raw mapping not affected by
        any overrides.

        The latest compose is chosen from the list of composes built for the
        release or linked to it. The RPM mapping of that compose is filtered to
        only include variants and architectures listed for the release.

        The used overrides come from the release specified in the URL, not the
        one for which the compose was originally built for.

        Following cases result in response of `404 NOT FOUND`:

         * no release with given id
         * release exists, but has no composes
         * release and compose exists, but there are no RPMs for the package

        __Response__:

            {
                "compose": string,
                "mapping": object
            }

        The `compose` key contains compose id of the compose used to populate
        the mapping.
        """
        release = get_object_or_404(models.Release, release_id=kwargs['release_id'])
        compose = release.get_latest_compose()
        if not compose:
            return Response(status=status.HTTP_404_NOT_FOUND,
                            data={'detail': 'Release %s has no composes' % kwargs['release_id']})
        mapping, _ = compose.get_rpm_mapping(kwargs['package'],
                                             bool(request.query_params.get('disable_overrides', False)),
                                             release=release)
        result = mapping.get_pure_dict()
        if not result:
            return Response(status=status.HTTP_404_NOT_FOUND,
                            data={'detail': 'Package %s not present in release %s'
                                  % (kwargs['package'], kwargs['release_id'])})
        return Response(data={'compose': compose.compose_id, 'mapping': result})


class ReleaseTypeViewSet(StrictQueryParamMixin,
                         mixins.ListModelMixin,
                         viewsets.GenericViewSet):
    """
    ##Overview##

    This page shows the usage of the **Release Types API**, please see the
    following for more details.

    ##Test tools##

    You can use ``curl`` in terminal, with -X _method_ (GET|POST|PUT|PATCH|DELETE),
    -d _data_ (a json string). or GUI plugins for
    browsers, such as ``RESTClient``, ``RESTConsole``.
    """
    queryset = models.ReleaseType.objects.all().order_by('id')
    serializer_class = ReleaseTypeSerializer
    filter_class = filters.ReleaseTypeFilter

    def list(self, request, *args, **kwargs):
        """
        __Method__: `GET`

        __URL__: $LINK:releasetype-list$

        __Query params__:

        %(FILTERS)s

        __Response__: a paged list of following objects

        %(SERIALIZER)s

        __Example__:

            $ curl "$URL:releasetype-list$"
            {
                "previous": null,
                "next": null,
                "count": 6,
                "results": [
                    {
                        "short": "ga",
                        "name": "Release",
                        "suffix": ""
                    },
                    ......
                ]
            }
        """
        return super(ReleaseTypeViewSet, self).list(request, *args, **kwargs)


class ReleaseVariantViewSet(ChangeSetModelMixin,
                            StrictQueryParamMixin,
                            MultiLookupFieldMixin,
                            viewsets.GenericViewSet):
    """
    This end-point provides access to Variants. Each variant is uniquely
    identified by release ID and variant UID. The pair in the form
    `release_id/variant_uid` is used in URL for retrieving, updating or
    deleting a single variant as well as in bulk operations.
    """
    queryset = models.Variant.objects.all().order_by('id')
    serializer_class = ReleaseVariantSerializer
    filter_class = filters.ReleaseVariantFilter
    lookup_fields = (('release__release_id', r'[^/]+'), ('variant_uid', r'[^/]+'))

    def create(self, *args, **kwargs):
        """
        __Method__: `POST`

        __URL__: $LINK:variant-list$

        __Data__:

        %(WRITABLE_SERIALIZER)s

        All fields are required. The required architectures must already be
        present in PDC.

        *type*: $LINK:varianttype-list$

        __Response__:

        %(SERIALIZER)s
        """
        return super(ReleaseVariantViewSet, self).create(*args, **kwargs)

    def update(self, *args, **kwargs):
        """
        __Method__: `PUT`

        __URL__: $LINK:variant-detail:release_id}/{variant_uid$

        __Data__:

        %(WRITABLE_SERIALIZER)s

        All attributes are required. The specified architectures will be set
        for this release. Also note that if you change the `uid`, the url for
        this variant will change.

        Changing the architectures may involve deleting some. Note that
        repositories are connected to some Variant.Arch pair and it is not
        possible to remove an arch with any repositories..

        *type*: $LINK:varianttype-list$

        __Response__:

        %(SERIALIZER)s
        """
        return super(ReleaseVariantViewSet, self).update(*args, **kwargs)

    def partial_update(self, *args, **kwargs):
        """
        __Method__: `PATCH`

        __URL__: $LINK:variant-detail:release_id}/{variant_uid$

        __Data__:

            {
                "release": string,
                "id": string,
                "uid": string,
                "name": string,
                "type": string,
                "arches": [string],
                "add_arches": [string],
                "remove_arches": [string]
            }

        All attributes are optional. If an attribute is not specified, that
        property of a variant will not change. The `arches` key can be used to
        set architectures associated with the variant. The `add_arches` key can
        list architectures to be added to current ones, with `remove_arches`
        some can be removed. While it is possible to combine `add_arches` with
        `remove_arches`, the `arches` attribute must not be combined with any
        other arch manipulation.

        If you try to remove architectures with associated repositories, the
        request will fail to do anything.

        __Response__:

        %(SERIALIZER)s
        """
        return super(ReleaseVariantViewSet, self).partial_update(*args, **kwargs)

    def list(self, *args, **kwargs):
        """
        __Method__: `GET`

        __URL__: $LINK:variant-list$

        __Query params__:

        %(FILTERS)s

        __Response__: a paged list of following objects

        %(SERIALIZER)s
        """
        return super(ReleaseVariantViewSet, self).list(*args, **kwargs)

    def retrieve(self, *args, **kwargs):
        """
        __Method__: `GET`

        __URL__: $LINK:variant-detail:release_id}/{variant_uid$

        __Response__:

        %(SERIALIZER)s
        """
        return super(ReleaseVariantViewSet, self).retrieve(*args, **kwargs)

    def destroy(self, *args, **kwargs):
        """
        This call will delete selected variant with all its arches. Please note
        that if there are any repositories filed under this variant, you will
        get an error `409 CONFLICT`.

        __Method__: `DELETE`

        __URL__: $LINK:variant-detail:release_id}/{variant_uid$
        """
        return super(ReleaseVariantViewSet, self).destroy(*args, **kwargs)


class VariantTypeViewSet(StrictQueryParamMixin,
                         mixins.ListModelMixin,
                         viewsets.GenericViewSet):
    """
    API endpoint that allows variant_types to be viewed.
    """
    serializer_class = VariantTypeSerializer
    queryset = models.VariantType.objects.all().order_by('id')

    def list(self, request, *args, **kwargs):
        """
        __Method__: GET

        __URL__: $LINK:varianttype-list$

        __Response__:

        %(SERIALIZER)s
        """
        return super(VariantTypeViewSet, self).list(request, *args, **kwargs)
